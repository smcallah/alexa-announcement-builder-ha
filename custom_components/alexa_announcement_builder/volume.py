"""Temporary Alexa device-volume management."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import ALEXA_DEVICES_DOMAIN, DOMAIN

_LOGGER = logging.getLogger(__name__)

_MEDIA_PLAYER_DOMAIN = "media_player"
_VOLUME_LEVEL = "volume_level"
_VOLUME_LOCKS = "volume_locks"
_VOLUME_ADJUSTMENTS = "volume_adjustments"
VOLUME_SETTLE_SECONDS = 1


@dataclass(eq=False)
class VolumeAdjustment:
    """One send's temporary volume on an Alexa media player.

    Identity matters: the latest send to a device owns its adjustment, and only
    the owner restores the original volume.
    """

    original_volume: float
    temporary_volume: float
    confirmed: bool = False


def _state_volume(hass: HomeAssistant, entity_id: str) -> float | None:
    """Return a valid media-player volume from Home Assistant state."""
    state = hass.states.get(entity_id)
    if state is None:
        return None
    volume = state.attributes.get(_VOLUME_LEVEL)
    if isinstance(volume, bool) or not isinstance(volume, int | float):
        return None
    volume = float(volume)
    if not 0 <= volume <= 1:
        return None
    return volume


def _volume_matches(current: float | None, expected: float) -> bool:
    """Return whether two Home Assistant volume levels effectively match."""
    return current is not None and abs(current - expected) < 0.005


def _media_player_ids(hass: HomeAssistant, notify_targets: Iterable[str]) -> list[str]:
    """Resolve notify targets to Alexa Devices media-player entities."""
    registry = er.async_get(hass)
    media_player_ids: set[str] = set()

    for target in notify_targets:
        notify_entry = registry.async_get(target)
        if notify_entry is None or notify_entry.device_id is None:
            _LOGGER.warning(
                "Cannot adjust volume for %s: no device registry entry", target
            )
            continue

        media_player = next(
            (
                entry
                for entry in er.async_entries_for_device(
                    registry, notify_entry.device_id
                )
                if entry.domain == _MEDIA_PLAYER_DOMAIN
                and entry.platform == ALEXA_DEVICES_DOMAIN
            ),
            None,
        )
        if media_player is None:
            _LOGGER.warning(
                "Cannot adjust volume for %s: no Alexa Devices media player",
                target,
            )
            continue
        media_player_ids.add(media_player.entity_id)

    return sorted(media_player_ids)


def _locks(hass: HomeAssistant, entity_ids: Iterable[str]) -> list[asyncio.Lock]:
    """Return stable per-device locks in entity-ID order."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    volume_locks: dict[str, asyncio.Lock] = domain_data.setdefault(_VOLUME_LOCKS, {})
    return [
        volume_locks.setdefault(entity_id, asyncio.Lock())
        for entity_id in sorted(entity_ids)
    ]


def _adjustments(hass: HomeAssistant) -> dict[str, VolumeAdjustment]:
    """Return the adjustments still waiting to be restored, by entity ID."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    return domain_data.setdefault(_VOLUME_ADJUSTMENTS, {})


@asynccontextmanager
async def _holding(locks: list[asyncio.Lock]) -> AsyncIterator[None]:
    """Hold every lock in order, releasing whichever were acquired."""
    acquired: list[asyncio.Lock] = []
    try:
        for lock in locks:
            await lock.acquire()
            acquired.append(lock)
        yield
    finally:
        for lock in reversed(acquired):
            lock.release()


async def _set_volume(hass: HomeAssistant, entity_id: str, volume_level: float) -> None:
    """Set one media player's device volume."""
    await hass.services.async_call(
        _MEDIA_PLAYER_DOMAIN,
        "volume_set",
        {_VOLUME_LEVEL: volume_level},
        target={"entity_id": entity_id},
        blocking=True,
    )


async def _restore_volumes(
    hass: HomeAssistant, adjusted: dict[str, VolumeAdjustment]
) -> None:
    """Restore devices this send still owns; callers hold their locks."""
    adjustments = _adjustments(hass)
    for entity_id, adjustment in adjusted.items():
        if adjustments.get(entity_id) is not adjustment:
            # A later send took over this device and will restore it.
            continue
        del adjustments[entity_id]

        current = _state_volume(hass, entity_id)
        if adjustment.confirmed and not _volume_matches(
            current, adjustment.temporary_volume
        ):
            _LOGGER.info(
                "Skipping volume restore for %s because its volume changed during "
                "the announcement",
                entity_id,
            )
            continue
        try:
            await _set_volume(hass, entity_id, adjustment.original_volume)
        except Exception:  # noqa: BLE001 - one restore must not block the others
            _LOGGER.exception("Failed to restore volume for %s", entity_id)


async def _shielded_restore(
    hass: HomeAssistant, adjusted: dict[str, VolumeAdjustment]
) -> None:
    """Complete volume restoration even if the calling task is cancelled."""
    restore_task = asyncio.create_task(_restore_volumes(hass, adjusted))
    try:
        await asyncio.shield(restore_task)
    except asyncio.CancelledError:
        await restore_task
        raise


async def _restore_after_delay(
    hass: HomeAssistant, adjusted: dict[str, VolumeAdjustment], restore_after: int
) -> None:
    """Wait for playback to finish, then restore the devices this send owns."""
    try:
        await asyncio.sleep(restore_after)
    finally:
        # Also restore when Home Assistant cancels the wait during shutdown.
        async with _holding(_locks(hass, adjusted)):
            await _shielded_restore(hass, adjusted)


@asynccontextmanager
async def temporary_device_volume(
    hass: HomeAssistant,
    notify_targets: Iterable[str],
    temporary_volume: float,
    restore_after: int,
) -> AsyncIterator[None]:
    """Raise Alexa volumes around a notification and restore each original value.

    The context exits as soon as the notification is sent. Restoration runs in a
    background task after ``restore_after`` seconds, or immediately if sending
    fails.
    """
    entity_ids = _media_player_ids(hass, notify_targets)
    adjustments = _adjustments(hass)
    adjusted: dict[str, VolumeAdjustment] = {}

    async with _holding(_locks(hass, entity_ids)):
        for entity_id in entity_ids:
            if (pending := adjustments.get(entity_id)) is not None:
                # The device is still at an earlier send's temporary volume.
                original_volume = pending.original_volume
            elif (original_volume := _state_volume(hass, entity_id)) is None:
                _LOGGER.warning(
                    "Cannot adjust volume for %s: current volume is unavailable",
                    entity_id,
                )
                continue
            try:
                await _set_volume(hass, entity_id, temporary_volume)
            except Exception:  # noqa: BLE001 - still notify other selected devices
                _LOGGER.exception("Failed to set temporary volume for %s", entity_id)
                continue
            adjustment = VolumeAdjustment(original_volume, temporary_volume)
            adjustments[entity_id] = adjustment
            adjusted[entity_id] = adjustment

        try:
            if adjusted:
                await asyncio.sleep(VOLUME_SETTLE_SECONDS)
                for entity_id, adjustment in adjusted.items():
                    adjustment.confirmed = _volume_matches(
                        _state_volume(hass, entity_id), temporary_volume
                    )
            yield
        except BaseException:
            if adjusted:
                await _shielded_restore(hass, adjusted)
            raise

    if adjusted:
        hass.async_create_background_task(
            _restore_after_delay(hass, adjusted, restore_after),
            f"{DOMAIN} volume restore",
        )

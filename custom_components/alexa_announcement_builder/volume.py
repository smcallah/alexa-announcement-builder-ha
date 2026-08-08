"""Temporary Alexa device-volume management."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_ALEXA_DEVICES = "alexa_devices"
_MEDIA_PLAYER_DOMAIN = "media_player"
_VOLUME_LEVEL = "volume_level"
_VOLUME_LOCKS = "volume_locks"
VOLUME_SETTLE_SECONDS = 1


@dataclass(frozen=True)
class VolumeSnapshot:
    """An Alexa media player's volume before an announcement."""

    entity_id: str
    volume_level: float


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
                and entry.platform == _ALEXA_DEVICES
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
        volume_locks.setdefault(entity_id, asyncio.Lock()) for entity_id in entity_ids
    ]


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
    hass: HomeAssistant,
    adjusted: list[VolumeSnapshot],
    temporary_volume: float,
    confirmed: set[str],
) -> None:
    """Restore volumes without masking an in-flight send exception."""
    for snapshot in adjusted:
        current = _state_volume(hass, snapshot.entity_id)
        if snapshot.entity_id in confirmed and not _volume_matches(
            current, temporary_volume
        ):
            _LOGGER.info(
                "Skipping volume restore for %s because its volume changed during "
                "the announcement",
                snapshot.entity_id,
            )
            continue
        try:
            await _set_volume(hass, snapshot.entity_id, snapshot.volume_level)
        except Exception:  # noqa: BLE001 - one restore must not block the others
            _LOGGER.exception("Failed to restore volume for %s", snapshot.entity_id)


async def _shielded_restore(
    hass: HomeAssistant,
    adjusted: list[VolumeSnapshot],
    temporary_volume: float,
    confirmed: set[str],
) -> None:
    """Complete volume restoration even if the service task is cancelled."""
    restore_task = asyncio.create_task(
        _restore_volumes(hass, adjusted, temporary_volume, confirmed)
    )
    try:
        await asyncio.shield(restore_task)
    except asyncio.CancelledError:
        await restore_task
        raise


@asynccontextmanager
async def temporary_device_volume(
    hass: HomeAssistant,
    notify_targets: Iterable[str],
    temporary_volume: float,
    restore_after: int,
) -> AsyncIterator[None]:
    """Raise Alexa volumes around a notification and restore each original value."""
    entity_ids = _media_player_ids(hass, notify_targets)
    locks = _locks(hass, entity_ids)
    acquired: list[asyncio.Lock] = []
    adjusted: list[VolumeSnapshot] = []
    confirmed: set[str] = set()

    try:
        for lock in locks:
            await lock.acquire()
            acquired.append(lock)

        snapshots = []
        for entity_id in entity_ids:
            volume = _state_volume(hass, entity_id)
            if volume is None:
                _LOGGER.warning(
                    "Cannot adjust volume for %s: current volume is unavailable",
                    entity_id,
                )
                continue
            snapshots.append(VolumeSnapshot(entity_id, volume))

        for snapshot in snapshots:
            try:
                await _set_volume(hass, snapshot.entity_id, temporary_volume)
            except Exception:  # noqa: BLE001 - still notify other selected devices
                _LOGGER.exception(
                    "Failed to set temporary volume for %s", snapshot.entity_id
                )
                continue
            adjusted.append(snapshot)

        if adjusted:
            await asyncio.sleep(VOLUME_SETTLE_SECONDS)
            confirmed = {
                snapshot.entity_id
                for snapshot in adjusted
                if _volume_matches(
                    _state_volume(hass, snapshot.entity_id), temporary_volume
                )
            }

        yield
        if adjusted:
            await asyncio.sleep(restore_after)
    finally:
        if adjusted:
            await _shielded_restore(hass, adjusted, temporary_volume, confirmed)
        for lock in reversed(acquired):
            lock.release()

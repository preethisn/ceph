import logging

try:
    from typing import List, Optional
except ImportError:
    pass

from ceph.deployment.inventory import Device

from ..inventory import Devices
from ..drive_group import DriveGroupSpec, DeviceSelection

from .filter import FilterGenerator

logger = logging.getLogger(__name__)


class DriveSelection(object):
    def __init__(self,
                 spec,  # type: DriveGroupSpec
                 disks,  # type: Devices
                 ):
        self.disks = disks.copy()
        self.spec = spec

        self._data = self.assign_devices(self.spec.data_devices)
        self._wal = self.assign_devices(self.spec.wal_devices)
        self._db = self.assign_devices(self.spec.db_devices)
        self._jornal = self.assign_devices(self.spec.journal_devices)

    def data_devices(self):
        # type: () -> List[Device]
        return self._data

    def wal_devices(self):
        # type: () -> List[Device]
        return self._wal

    def db_devices(self):
        # type: () -> List[Device]
        return self._db

    def journal_devices(self):
        # type: () -> List[Device]
        return self._jornal

    @staticmethod
    def _limit_reached(device_filter, len_devices,
                       disk_path):
        # type: (DeviceSelection, int, str) -> bool
        """ Check for the <limit> property and apply logic

        If a limit is set in 'device_attrs' we have to stop adding
        disks at some point.

        If limit is set (>0) and len(devices) >= limit

        :param int len_devices: Length of the already populated device set/list
        :param str disk_path: The disk identifier (for logging purposes)
        :return: True/False if the device should be added to the list of devices
        :rtype: bool
        """
        limit = device_filter.limit or 0

        if limit > 0 and len_devices >= limit:
            logger.info("Refuse to add {} due to limit policy of <{}>".format(
                disk_path, limit))
            return True
        return False

    @staticmethod
    def _has_mandatory_idents(disk):
        # type: (Device) -> bool
        """ Check for mandatory indentification fields
        """
        if disk.path:
            logger.debug("Found matching disk: {}".format(disk.path))
            return True
        else:
            raise Exception(
                "Disk {} doesn't have a 'path' identifier".format(disk))

    def assign_devices(self, device_filter):
        # type: (Optional[DeviceSelection]) -> List[Device]
        """ Assign drives based on used filters

        Do not add disks when:

        1) Filter didn't match
        2) Disk doesn't have a mandatory identification item (path)
        3) The set :limit was reached

        After the disk was added we make sure not to re-assign this disk
        for another defined type[wal/db/journal devices]

        return a sorted(by path) list of devices
        """
        if device_filter is None:
            logger.debug('device_filter is None')
            return []
        devices = list()  # type: List[Device]
        for _filter in FilterGenerator(device_filter):
            if not _filter.is_matchable:
                logger.debug(
                    "Ignoring disk {}. Filter is not matchable".format(
                        device_filter))
                continue

            for disk in self.disks.devices:
                logger.debug("Processing disk {}".format(disk.path))

                # continue criterias
                assert _filter.matcher is not None
                if not _filter.matcher.compare(disk):
                    logger.debug(
                        "Ignoring disk {}. Filter did not match".format(
                            disk.path))
                    continue

                if not self._has_mandatory_idents(disk):
                    logger.debug(
                        "Ignoring disk {}. Missing mandatory idents".format(
                            disk.path))
                    continue

                # break on this condition.
                if self._limit_reached(device_filter, len(devices), disk.path):
                    logger.debug("Ignoring disk {}. Limit reached".format(
                        disk.path))
                    break

                if disk not in devices:
                    logger.debug('Adding disk {}'.format(disk.path))
                    devices.append(disk)

        # This disk is already taken and must not be re-assigned.
        for taken_device in devices:
            if taken_device in self.disks.devices:
                self.disks.devices.remove(taken_device)

        return sorted([x for x in devices], key=lambda dev: dev.path)

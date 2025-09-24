from collections import defaultdict

import structlog

logger = structlog.get_logger()


class UserMapping:
    """
    Mapping between user IDs and channel IDs.
    """

    def __init__(self):
        self.user_id_to_channel_ids: dict[str, set[str]] = defaultdict(set)
        self.channel_id_to_user_ids: dict[str, set[str]] = defaultdict(set)

    def add_mapping(self, user_id: str, channel_id: str):
        """
        Add a mapping between a user ID and a channel ID.
        """
        self.user_id_to_channel_ids[user_id].add(channel_id)
        self.channel_id_to_user_ids[channel_id].add(user_id)

    def get_user_channel_ids(self, user_id: str) -> list[str]:
        """
        Get the channel IDs for a user ID.
        """
        return self.user_id_to_channel_ids.get(user_id, [])

    def get_channel_user_ids(self, channel_id: str) -> list[str]:
        """
        Get the user IDs for a channel ID.
        """
        return self.channel_id_to_user_ids.get(channel_id, [])

    def get_all_channel_ids(self) -> list[str]:
        """
        Get all channel IDs.
        """
        return list(self.channel_id_to_user_ids.keys())

    def remove_user_from_channels(self, user_id: str) -> list[str]:
        """
        Remove a user from all channels. If a channel is empty, remove it.
        """
        channel_ids = self.user_id_to_channel_ids.pop(user_id, [])
        empty_channel_ids = []
        for channel_id in channel_ids:
            self.channel_id_to_user_ids[channel_id].remove(user_id)
            if not self.channel_id_to_user_ids[channel_id]:
                empty_channel_ids.append(channel_id)
        for channel_id in empty_channel_ids:
            self.channel_id_to_user_ids.pop(channel_id)
        logger.info(f"Empty channel IDs: {empty_channel_ids}")
        return empty_channel_ids

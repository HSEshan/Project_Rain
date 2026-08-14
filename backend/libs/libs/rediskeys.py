class RediKeys:
    @staticmethod
    def user_grpc_endpoint(user_id: str) -> str:
        return f"user:{user_id}:grpc_endpoint"

    @staticmethod
    def user_channels(user_id: str) -> str:
        return f"user:{user_id}:channels"

    @staticmethod
    def channel_grpc_endpoints(channel_id: str) -> str:
        return f"channel:{channel_id}:grpc_endpoints"

    @staticmethod
    def channel_voice_members(channel_id: str) -> str:
        """Users currently connected to a voice channel's SFU room.

        Written by rest_api on voice join/leave. It is a cache of what LiveKit
        knows, kept so that a client can render "who is in here" without
        connecting to the room first.
        """
        return f"channel:{channel_id}:voice_members"

    @staticmethod
    def stream_shard(shard_id: str) -> str:
        return f"stream_shard:{shard_id}"

    @staticmethod
    def heartbeat(consumer_id: str) -> str:
        return f"heartbeat:{consumer_id}"

    @staticmethod
    def event_consumers() -> str:
        return "event_consumers"

    @staticmethod
    def leases() -> str:
        return "leases"

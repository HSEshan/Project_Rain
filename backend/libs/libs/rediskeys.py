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
    def rate_limit(rule: str, identity: str) -> str:
        return f"ratelimit:{rule}:{identity}"

    @staticmethod
    def stream_shard(shard_id: str) -> str:
        return f"stream_shard:{shard_id}"

    @staticmethod
    def heartbeat(consumer_id: str) -> str:
        return f"heartbeat:{consumer_id}"

    @staticmethod
    def gateway_heartbeat(grpc_endpoint: str) -> str:
        """Present while the gateway advertising `grpc_endpoint` is alive.

        Written by the gateway with a short TTL and refreshed, so a gateway that
        is SIGKILLed or OOM-killed simply stops having one. The consumer reads it
        only after a delivery to that endpoint has failed, to tell a gateway that
        is gone from one that is merely slow.
        """
        return f"gateway:{grpc_endpoint}:heartbeat"

    @staticmethod
    def event_consumers() -> str:
        return "event_consumers"

    @staticmethod
    def leases() -> str:
        return "leases"

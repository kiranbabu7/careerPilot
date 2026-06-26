"""Memory and activity persistence."""

from apps.memory.models import ActivityEvent, MemoryEntry


class MemoryRepository:
    def create_entry(
        self,
        *,
        user,
        category: str,
        content: str,
        metadata: dict | None = None,
    ) -> MemoryEntry:
        return MemoryEntry.objects.create(
            user=user,
            category=category,
            content=content,
            metadata=metadata or {},
        )

    def list_for_user(self, user, limit: int = 50) -> list[MemoryEntry]:
        return list(MemoryEntry.objects.filter(user=user).order_by("-created_at")[:limit])

    def get_context(self, user) -> dict:
        entries = self.list_for_user(user, limit=20)
        return {
            "user_id": str(user.id),
            "memories": [
                {
                    "id": str(entry.id),
                    "category": entry.category,
                    "content": entry.content,
                    "metadata": entry.metadata,
                    "created_at": entry.created_at.isoformat(),
                }
                for entry in entries
            ],
        }


class ActivityRepository:
    def create_event(
        self,
        *,
        user,
        event_type: str,
        title: str,
        description: str = "",
        metadata: dict | None = None,
    ) -> ActivityEvent:
        return ActivityEvent.objects.create(
            user=user,
            event_type=event_type,
            title=title,
            description=description,
            metadata=metadata or {},
        )

    def list_recent(self, user, limit: int = 20) -> list[ActivityEvent]:
        return list(
            ActivityEvent.objects.filter(user=user).order_by("-created_at")[:limit]
        )

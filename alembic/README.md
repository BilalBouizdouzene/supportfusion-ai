# Database migrations

The MVP bootstraps SQLite with `Base.metadata.create_all()` for a zero-command
local start. Alembic is included for controlled upgrades and reviewed schema
history:

```powershell
alembic upgrade head
alembic revision --autogenerate -m "describe the change"
```


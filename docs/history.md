# History

Background that is not obvious from the code. Newest first.

- **Money with 4 decimals** - the first Alembic schema used `Numeric(12, 2)`, and databases older than
  Alembic were stamped at head with FLOAT columns. Migration `c4d5e6f7a8b9` moved every money column
  to `Numeric(12, 4)` so that split items like 0.3975 stay exact.
- **`Decimal(str(...))` everywhere** - MariaDB/PyMySQL handed `Numeric` columns back as `float`, and
  `float - Decimal` raised `TypeError` (HTTP 500) when adding, editing or deleting transactions.
- **`html` shadowing** - scheduled emails crashed because a local variable named `html` shadowed the
  stdlib module that `html.escape()` needs.
- **Admin hidden from the dashboard** - the site admin acts as the bank; her balance is always the
  negative sum of everyone else's, so the dashboard and the admin summary email leave her out.
- **Blueprints** - the backend started as a single ~2300-line `app.py`; it was split into
  `routes/` blueprints plus service modules, with unbound extension instances in `extensions.py`
  to avoid circular imports.
- **HANDOVER.md** became CLAUDE.md.

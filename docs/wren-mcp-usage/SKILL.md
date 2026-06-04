---
name: wren-mcp-usage
description: "Wren Semantic Engine MCP usage guide. Query data through the MDL semantic layer via MCP tools — discover models, write SQL, verify with dry-plan, execute, and recover from errors. Use when: user asks a data question, requests a report or analysis, asks about metrics, revenue, customers, orders, trends, or any business data; user says 'how many', 'show me', 'what is the', 'top N', 'compare', 'trend', 'growth', 'breakdown'; user wants to explore, analyze, filter, aggregate, or summarize data from a database through Wren's MCP server."
---

# Wren MCP — Agent Query Guide

## Prerequisites

This skill requires the **wren** MCP server to be enabled in the conversation. The MCP server provides 4 tools prefixed with `mcp__wren__`. If these tools are not available, remind the user to upload and enable the wren MCP server first.

## Overview

You have access to 4 Wren MCP tools. The server wraps WrenEngine — it accepts SQL written against MDL **model names** (not raw database tables) and translates through the semantic layer to the target dialect.

| Tool | Purpose |
|------|---------|
| `mcp__wren__wren_list_models` | List all available models and column counts |
| `mcp__wren__wren_describe_model` | Get a model's columns, types, and descriptions |
| `mcp__wren__wren_dry_plan` | Expand SQL through the semantic layer without executing — shows generated SQL |
| `mcp__wren__wren_query` | Execute SQL through the semantic layer, return results as text table |

The manifest (MDL) and database connection are pre-configured when the MCP server starts. You don't manage profiles or build contexts — you query.

---

## Workflow 1: Answering a data question

### Step 1 — Discover the schema

Start by understanding what's available. Unless the user already named specific models:

1. Call `mcp__wren__wren_list_models` to see all models and their column counts.
2. For each model that looks relevant to the question, call `mcp__wren__wren_describe_model` to see its columns, types, and descriptions.

**Example:**

The user asks "what were total sales by customer last month?" — you need orders and customers.

```
→ mcp__wren__wren_list_models()
← - orders (9 columns)
  - customer (8 columns)
  - lineitem (16 columns)
  - part (9 columns)
  - supplier (7 columns)

→ mcp__wren__wren_describe_model(model_name="orders")
← # orders
    - o_orderkey (int64) — Primary key
    - o_custkey (int64) — Foreign key to customer
    - o_totalprice (float64) — Total order amount
    - o_orderstatus (varchar) — Order status
    - o_orderdate (date) — Date of order
    ...

→ mcp__wren__wren_describe_model(model_name="customer")
← # customer
    - c_custkey (int64) — Primary key
    - c_name (varchar) — Customer name
    ...
```

Key information to extract from descriptions:
- Column types — use these for type-aware SQL (dates, numerics, strings)
- Primary/foreign key hints — tells you how models relate (even without explicit relationships in the description)
- Business meaning from descriptions — trust these over column names

### Step 2 — Assess complexity

Before writing SQL, decide whether to verify first or execute directly.

**Execute directly** when:
- Single model, simple aggregation (COUNT, SUM, AVG) with GROUP BY
- Simple filter + sort + limit
- The query is trivial and you're confident about model/column names

**Verify with dry-plan first** when:
- JOINs across multiple models (especially if relationship isn't documented in descriptions)
- Subqueries, CTEs, or window functions
- Complex WHERE clauses with nested conditions
- Any query where getting it wrong would be expensive (large tables, remote warehouse)
- You're uncertain about column names or types

### Step 3 — Write and execute SQL

**SQL rules:**
- Target **MDL model names**, not raw database tables
- Write dialect-neutral SQL — the engine translates to the target dialect
- Qualify columns with model names when ambiguous: `orders.o_orderkey`, not just `o_orderkey`
- Always use `LIMIT` for exploratory queries — prevents accidental full-table scans

**Simple query — execute directly:**

```
→ mcp__wren__wren_query(sql="SELECT c_name, SUM(o_totalprice) AS total
     FROM orders JOIN customer ON orders.o_custkey = customer.c_custkey
     GROUP BY 1 ORDER BY 2 DESC", limit=10)
←     c_name       total
    Customer#1   12345.67
    Customer#2    9876.54
    ...
```

**Complex query — verify first:**

```
→ mcp__wren__wren_dry_plan(sql="SELECT ...")
← WITH model_orders AS (
    SELECT o_orderkey, o_custkey, o_totalprice, ...
    FROM db.schema.orders
  ),
  model_customer AS (
    SELECT c_custkey, c_name, ...
    FROM db.schema.customer
  )
  SELECT c_name, SUM(model_orders.o_totalprice) AS total
  FROM model_orders JOIN model_customer ON ...
  GROUP BY 1 ORDER BY 2 DESC
```

Check the expanded SQL:
- Are the correct models referenced in the CTEs?
- Do JOINs use the right keys?
- Are column names resolved correctly?

If the expanded SQL looks correct, execute:

```
→ mcp__wren__wren_query(sql="SELECT ...", limit=10)
```

### Step 4 — Present results

Present results clearly to the user. If the result set is large, summarize key findings. If the user asks a follow-up question, treat it as a new query starting from Step 1 (reuse schema knowledge already gathered).

---

## Workflow 2: Error recovery

### "Model not found" or "table not found"

The SQL references a name that isn't in the MDL.

1. Call `mcp__wren__wren_list_models` — see the exact model names available.
2. Match the user's intent to the closest model name.
3. Use the MDL model name exactly as listed.

### "Column 'X' not found in model 'Y'"

The column name doesn't match what's in the MDL.

1. Call `mcp__wren__wren_describe_model(model_name="Y")` — see all available columns.
2. Find the correct column name from the description.
3. Fix the SQL and retry.

### "Ambiguous column 'X'"

The column exists in multiple models in the query.

1. Qualify it with the model name: `ModelName.column_name`.
2. Re-run.

### Type mismatch or function error

The query passed dry-plan but failed on execution (database error).

1. Call `mcp__wren__wren_dry_plan(sql="<failed SQL>")` — see the generated SQL.
2. Call `mcp__wren__wren_describe_model` for the relevant model — check the column types.
3. Match the error to the type:
   - Type mismatch → add explicit CAST in your SQL
   - Function not supported → use a simpler, dialect-neutral alternative
   - Division by zero → add NULLIF or CASE
4. Fix and retry.

### Dry-plan fails

The MDL layer can't resolve your SQL. The error message tells you exactly what's wrong:

| Error | Cause | Fix |
|-------|-------|-----|
| `model 'X' not found` | Wrong model name | `mcp__wren__wren_list_models` to find correct name |
| `column 'X' not found` | Wrong column name | `mcp__wren__wren_describe_model` to find correct name |
| `ambiguous column 'X'` | Column in multiple models | Qualify with `ModelName.column` |
| Planning error with JOIN | Relationship not in MDL | Check `mcp__wren__wren_describe_model` for FK hints, write explicit JOIN condition |

Fix one issue at a time. Re-run dry-plan after each fix to see if new errors surface.

---

## Decision tree

```
User asks a data question
  │
  ├─→ Known models / columns? (user named them, or from earlier in session)
  │     └─→ Yes → Jump to "Write SQL"
  │
  └─→ No → mcp__wren__wren_list_models()
            │
            └─→ For each relevant model: mcp__wren__wren_describe_model(name)
                  │
                  └─→ Write SQL against model names
                        │
                        ├─→ Simple? → mcp__wren__wren_query(sql, limit=N)
                        │
                        └─→ Complex? → mcp__wren__wren_dry_plan(sql)
                              │
                              ├─→ Looks correct → mcp__wren__wren_query(sql, limit=N)
                              │
                              └─→ Looks wrong → Fix → re-run dry-plan
```

---

## Things to avoid

- **Do not guess model or column names** — always discover via `mcp__wren__wren_list_models` + `mcp__wren__wren_describe_model` first
- **Do not reference raw database table names** — always use MDL model names
- **Do not skip `mcp__wren__wren_dry_plan` for complex queries** — verifying the generated SQL is cheap; executing wrong SQL on a large table is expensive
- **Do not execute without a LIMIT on exploratory queries** — use `limit=50` or similar to avoid accidental full scans
- **Do not assume column types from names alone** — `mcp__wren__wren_describe_model` shows actual types; use them
- **Do not write dialect-specific SQL** — the engine translates; stick to standard SQL
- **Do not retry a failing query more than twice without changing approach** — after two failures, re-examine the schema with `mcp__wren__wren_describe_model` before a third attempt
- **Do not invent models or columns that don't exist** — if the schema doesn't cover the question, tell the user what's available and what's missing

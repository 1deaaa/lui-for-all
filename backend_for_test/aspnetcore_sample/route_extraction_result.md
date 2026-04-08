# Route Extraction Result: aspnetcore_sample

- Adapter: aspnet_core
- Source Path: C:\Users\SERVER\Desktop\lui-for-all\backend_for_test\aspnetcore_sample
- Route Count: 7

## Route List

1. GET:/api/items | GET /api/items | Program.cs:20-20
2. POST:/api/items | POST /api/items | Program.cs:21-26
3. PUT:/api/items/{id} | PUT /api/items/{id} | Program.cs:27-39
4. PATCH:/api/items/{id} | PATCH /api/items/{id} | Program.cs:40-50
5. DELETE:/api/items/{id} | DELETE /api/items/{id} | Program.cs:51-61
6. HEAD:/api/health | HEAD /api/health | Program.cs:62-62
7. OPTIONS:/api/health | OPTIONS /api/health | Program.cs:63-63

## Function Implementation Blocks

### GET:/api/items

```text
app.MapGet("/api/items", () => Results.Ok(new { route = "GET /api/items", total = items.Count, items = Snapshot() }));
```

### POST:/api/items

```text
app.MapPost("/api/items", () =>
{
	var id = (items.Count + 1).ToString();
	items.Add(BuildItem(id, $"item-{id}", "created"));
	return Results.Ok(new { route = "POST /api/items", total = items.Count });
});
```

### PUT:/api/items/{id}

```text
app.MapPut("/api/items/{id}", (string id) =>
{
	var current = FindItem(id);
	if (current is not null)
	{
		current["name"] = $"{current["name"]}-v2";
		current["status"] = "replaced";
		return Results.Ok(new { route = $"PUT /api/items/{id}", item = current });
	}

	items.Add(BuildItem(id, $"item-{id}", "inserted"));
	return Results.Ok(new { route = $"PUT /api/items/{id}", inserted = true, total = items.Count });
});
```

### PATCH:/api/items/{id}

```text
app.MapPatch("/api/items/{id}", (string id) =>
{
	var current = FindItem(id);
	if (current is null)
	{
		return Results.NotFound(new { route = $"PATCH /api/items/{id}", missing = true });
	}

	current["status"] = "patched";
	return Results.Ok(new { route = $"PATCH /api/items/{id}", item = current });
});
```

### DELETE:/api/items/{id}

```text
app.MapDelete("/api/items/{id}", (string id) =>
{
	var current = FindItem(id);
	if (current is not null)
	{
		items.Remove(current);
		return Results.Ok(new { route = $"DELETE /api/items/{id}", removed = true, total = items.Count });
	}

	return Results.NotFound(new { route = $"DELETE /api/items/{id}", removed = false });
});
```

### HEAD:/api/health

```text
app.MapHead("/api/health", () => Results.Ok());
```

### OPTIONS:/api/health

```text
app.MapMethods("/api/health", new[] { "OPTIONS" }, () => Results.Ok(new { route = "OPTIONS /api/health", total = items.Count }));
```

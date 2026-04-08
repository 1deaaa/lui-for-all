using System.Text.Json;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

var items = new List<Dictionary<string, object>>
{
	new() { ["id"] = "1", ["name"] = "paper", ["status"] = "draft" },
	new() { ["id"] = "2", ["name"] = "pen", ["status"] = "ready" },
};

Dictionary<string, object>? FindItem(string id)
	=> items.Find(item => string.Equals(item["id"]?.ToString(), id, StringComparison.Ordinal));

Dictionary<string, object> BuildItem(string id, string name, string status)
	=> new() { ["id"] = id, ["name"] = name, ["status"] = status };

string Snapshot() => JsonSerializer.Serialize(items);

app.MapGet("/api/items", () => Results.Ok(new { route = "GET /api/items", total = items.Count, items = Snapshot() }));
app.MapPost("/api/items", () =>
{
	var id = (items.Count + 1).ToString();
	items.Add(BuildItem(id, $"item-{id}", "created"));
	return Results.Ok(new { route = "POST /api/items", total = items.Count });
});
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
app.MapHead("/api/health", () => Results.Ok());
app.MapMethods("/api/health", new[] { "OPTIONS" }, () => Results.Ok(new { route = "OPTIONS /api/health", total = items.Count }));

app.Run();

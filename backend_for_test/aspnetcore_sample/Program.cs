var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

app.MapGet("/api/items", () => Results.Ok("GET /api/items"));
app.MapPost("/api/items", () => Results.Ok("POST /api/items"));
app.MapPut("/api/items/{id}", (string id) => Results.Ok($"PUT /api/items/{id}"));
app.MapPatch("/api/items/{id}", (string id) => Results.Ok($"PATCH /api/items/{id}"));
app.MapDelete("/api/items/{id}", (string id) => Results.Ok($"DELETE /api/items/{id}"));
app.MapHead("/api/health", () => Results.Ok());
app.MapMethods("/api/health", new[] { "OPTIONS" }, () => Results.Ok());

app.Run();

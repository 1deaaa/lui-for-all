# Route Extraction Result: go_gin_sample

- Adapter: go_web
- Source Path: C:\Users\SERVER\Desktop\lui-for-all\backend_for_test\go_gin_sample
- Route Count: 7

## Route List

1. GET:/api/items | GET /api/items | main.go:47-50
2. POST:/api/items | POST /api/items | main.go:51-56
3. PUT:/api/items/{id} | PUT /api/items/{id} | main.go:57-70
4. PATCH:/api/items/{id} | PATCH /api/items/{id} | main.go:71-82
5. DELETE:/api/items/{id} | DELETE /api/items/{id} | main.go:83-94
6. HEAD:/api/health | HEAD /api/health | main.go:95-99
7. OPTIONS:/api/health | OPTIONS /api/health | main.go:100-104

## Function Implementation Blocks

### GET:/api/items

```text

func getItems(c *gin.Context) {
    c.JSON(http.StatusOK, gin.H{"route": "GET /api/items", "total": len(items), "items": snapshotItems()})
}
```

### POST:/api/items

```text

func createItem(c *gin.Context) {
    id := strconv.Itoa(len(items) + 1)
    items = append(items, item{ID: id, Name: "item-" + id, Status: "created"})
    c.JSON(http.StatusCreated, gin.H{"route": "POST /api/items", "total": len(items)})
}
```

### PUT:/api/items/{id}

```text

func replaceItem(c *gin.Context) {
    id := c.Param("id")
    current, _ := findItem(id)
    if current != nil {
        current.Name = current.Name + "-v2"
        current.Status = "replaced"
        c.JSON(http.StatusOK, gin.H{"route": "PUT /api/items/:id", "item": current})
        return
    }

    items = append(items, item{ID: id, Name: "item-" + id, Status: "inserted"})
    c.JSON(http.StatusOK, gin.H{"route": "PUT /api/items/:id", "inserted": true, "total": len(items)})
}
```

### PATCH:/api/items/{id}

```text

func patchItem(c *gin.Context) {
    id := c.Param("id")
    current, _ := findItem(id)
    if current == nil {
        c.JSON(http.StatusNotFound, gin.H{"route": "PATCH /api/items/:id", "missing": true})
        return
    }

    current.Status = "patched"
    c.JSON(http.StatusOK, gin.H{"route": "PATCH /api/items/:id", "item": current})
}
```

### DELETE:/api/items/{id}

```text

func deleteItem(c *gin.Context) {
    id := c.Param("id")
    _, idx := findItem(id)
    if idx >= 0 {
        items = append(items[:idx], items[idx+1:]...)
        c.JSON(http.StatusOK, gin.H{"route": "DELETE /api/items/:id", "removed": true, "total": len(items)})
        return
    }

    c.JSON(http.StatusNotFound, gin.H{"route": "DELETE /api/items/:id", "removed": false})
}
```

### HEAD:/api/health

```text

func headHealth(c *gin.Context) {
    c.Header("X-Sample-Items", strconv.Itoa(len(items)))
    c.Status(http.StatusOK)
}
```

### OPTIONS:/api/health

```text

func optionsHealth(c *gin.Context) {
    c.Header("Allow", "GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS")
    c.JSON(http.StatusOK, gin.H{"route": "OPTIONS /api/health", "total": len(items)})
}
```

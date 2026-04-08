package main

import (
    "net/http"
    "strconv"

    "github.com/gin-gonic/gin"
)

type item struct {
    ID     string `json:"id"`
    Name   string `json:"name"`
    Status string `json:"status"`
}

var items = []item{
    {ID: "1", Name: "paper", Status: "draft"},
    {ID: "2", Name: "pen", Status: "ready"},
}

func snapshotItems() []item {
    copied := make([]item, len(items))
    copy(copied, items)
    return copied
}

func findItem(id string) (*item, int) {
    for idx := range items {
        if items[idx].ID == id {
            return &items[idx], idx
        }
    }
    return nil, -1
}

func registerRoutes(r *gin.Engine) {
    api := r.Group("/api")

    api.GET("/items", getItems)
    api.POST("/items", createItem)
    api.PUT("/items/:id", replaceItem)
    api.PATCH("/items/:id", patchItem)
    api.DELETE("/items/:id", deleteItem)
    api.HEAD("/health", headHealth)
    api.OPTIONS("/health", optionsHealth)
}

func getItems(c *gin.Context) {
    c.JSON(http.StatusOK, gin.H{"route": "GET /api/items", "total": len(items), "items": snapshotItems()})
}

func createItem(c *gin.Context) {
    id := strconv.Itoa(len(items) + 1)
    items = append(items, item{ID: id, Name: "item-" + id, Status: "created"})
    c.JSON(http.StatusCreated, gin.H{"route": "POST /api/items", "total": len(items)})
}

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

func headHealth(c *gin.Context) {
    c.Header("X-Sample-Items", strconv.Itoa(len(items)))
    c.Status(http.StatusOK)
}

func optionsHealth(c *gin.Context) {
    c.Header("Allow", "GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS")
    c.JSON(http.StatusOK, gin.H{"route": "OPTIONS /api/health", "total": len(items)})
}

func main() {
    r := gin.Default()
    registerRoutes(r)
    _ = r
}

package main

import "github.com/gin-gonic/gin"

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

func getItems(c *gin.Context) {}
func createItem(c *gin.Context) {}
func replaceItem(c *gin.Context) {}
func patchItem(c *gin.Context) {}
func deleteItem(c *gin.Context) {}
func headHealth(c *gin.Context) {}
func optionsHealth(c *gin.Context) {}

func main() {
    r := gin.Default()
    registerRoutes(r)
    _ = r
}

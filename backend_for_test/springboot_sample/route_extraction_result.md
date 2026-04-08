# Route Extraction Result: springboot_sample

- Adapter: java_spring
- Source Path: C:\Users\SERVER\Desktop\lui-for-all\backend_for_test\springboot_sample
- Route Count: 7

## Route List

1. GET:/api/items | GET /api/items | src\main\java\com\example\demo\SampleController.java:48-51
2. POST:/api/items | POST /api/items | src\main\java\com\example\demo\SampleController.java:53-58
3. PUT:/api/items/{id} | PUT /api/items/{id} | src\main\java\com\example\demo\SampleController.java:60-70
4. PATCH:/api/items/{id} | PATCH /api/items/{id} | src\main\java\com\example\demo\SampleController.java:72-80
5. DELETE:/api/items/{id} | DELETE /api/items/{id} | src\main\java\com\example\demo\SampleController.java:82-90
6. HEAD:/api/health | HEAD /api/health | src\main\java\com\example\demo\SampleController.java:92-95
7. OPTIONS:/api/health | OPTIONS /api/health | src\main\java\com\example\demo\SampleController.java:92-95

## Function Implementation Blocks

### GET:/api/items

```text
@GetMapping("/items")
    public String listItems() {
        return "GET /api/items -> " + snapshotItems();
    }
```

### POST:/api/items

```text
@PostMapping("/items")
    public String createItem() {
        String id = String.valueOf(ITEMS.size() + 1);
        ITEMS.add(item(id, "item-" + id, "created"));
        return "POST /api/items -> total=" + ITEMS.size();
    }
```

### PUT:/api/items/{id}

```text
@PutMapping("/items/{id}")
    public String replaceItem(@PathVariable String id) {
        Map<String, Object> current = findItem(id);
        if (current != null) {
            current.put("name", current.get("name") + "-v2");
            current.put("status", "replaced");
            return "PUT /api/items/" + id + " -> " + current;
        }
        ITEMS.add(item(id, "item-" + id, "inserted"));
        return "PUT /api/items/" + id + " -> inserted";
    }
```

### PATCH:/api/items/{id}

```text
@PatchMapping("/items/{id}")
    public String patchItem(@PathVariable String id) {
        Map<String, Object> current = findItem(id);
        if (current == null) {
            return "PATCH /api/items/" + id + " -> missing";
        }
        current.put("status", "patched");
        return "PATCH /api/items/" + id + " -> " + current;
    }
```

### DELETE:/api/items/{id}

```text
@DeleteMapping("/items/{id}")
    public String deleteItem(@PathVariable String id) {
        Map<String, Object> current = findItem(id);
        if (current != null) {
            ITEMS.remove(current);
            return "DELETE /api/items/" + id + " -> removed";
        }
        return "DELETE /api/items/" + id + " -> missing";
    }
```

### HEAD:/api/health

```text
@RequestMapping(value = "/health", method = {RequestMethod.HEAD, RequestMethod.OPTIONS})
    public String healthMeta() {
        return "HEAD/OPTIONS /api/health -> items=" + ITEMS.size();
    }
```

### OPTIONS:/api/health

```text
@RequestMapping(value = "/health", method = {RequestMethod.HEAD, RequestMethod.OPTIONS})
    public String healthMeta() {
        return "HEAD/OPTIONS /api/health -> items=" + ITEMS.size();
    }
```

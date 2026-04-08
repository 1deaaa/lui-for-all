package com.example.demo;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class SampleController {

    private static final List<Map<String, Object>> ITEMS = new CopyOnWriteArrayList<>(List.of(
        item("1", "paper", "draft"),
        item("2", "pen", "ready")
    ));

    private static Map<String, Object> item(String id, String name, String status) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("id", id);
        value.put("name", name);
        value.put("status", status);
        return value;
    }

    private static Map<String, Object> findItem(String id) {
        for (Map<String, Object> current : ITEMS) {
            if (id.equals(String.valueOf(current.get("id")))) {
                return current;
            }
        }
        return null;
    }

    private static String snapshotItems() {
        return ITEMS.toString();
    }

    @GetMapping("/items")
    public String listItems() {
        return "GET /api/items -> " + snapshotItems();
    }

    @PostMapping("/items")
    public String createItem() {
        String id = String.valueOf(ITEMS.size() + 1);
        ITEMS.add(item(id, "item-" + id, "created"));
        return "POST /api/items -> total=" + ITEMS.size();
    }

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

    @PatchMapping("/items/{id}")
    public String patchItem(@PathVariable String id) {
        Map<String, Object> current = findItem(id);
        if (current == null) {
            return "PATCH /api/items/" + id + " -> missing";
        }
        current.put("status", "patched");
        return "PATCH /api/items/" + id + " -> " + current;
    }

    @DeleteMapping("/items/{id}")
    public String deleteItem(@PathVariable String id) {
        Map<String, Object> current = findItem(id);
        if (current != null) {
            ITEMS.remove(current);
            return "DELETE /api/items/" + id + " -> removed";
        }
        return "DELETE /api/items/" + id + " -> missing";
    }

    @RequestMapping(value = "/health", method = {RequestMethod.HEAD, RequestMethod.OPTIONS})
    public String healthMeta() {
        return "HEAD/OPTIONS /api/health -> items=" + ITEMS.size();
    }
}

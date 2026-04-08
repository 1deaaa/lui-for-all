package com.example.demo;

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

    @GetMapping("/items")
    public String listItems() {
        return "GET /api/items";
    }

    @PostMapping("/items")
    public String createItem() {
        return "POST /api/items";
    }

    @PutMapping("/items/{id}")
    public String replaceItem(@PathVariable String id) {
        return "PUT /api/items/" + id;
    }

    @PatchMapping("/items/{id}")
    public String patchItem(@PathVariable String id) {
        return "PATCH /api/items/" + id;
    }

    @DeleteMapping("/items/{id}")
    public String deleteItem(@PathVariable String id) {
        return "DELETE /api/items/" + id;
    }

    @RequestMapping(value = "/health", method = {RequestMethod.HEAD, RequestMethod.OPTIONS})
    public String healthMeta() {
        return "HEAD/OPTIONS /api/health";
    }
}

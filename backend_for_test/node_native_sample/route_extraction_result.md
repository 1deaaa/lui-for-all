# Route Extraction Result: node_native_sample

- Adapter: nodejs_typescript
- Source Path: C:\Users\SERVER\Desktop\lui-for-all\backend_for_test\node_native_sample
- Route Count: 7

## Route List

1. GET:/api/items | GET /api/items | server.js:22-24
2. POST:/api/items | POST /api/items | server.js:26-30
3. PUT:/api/items/{id} | PUT /api/items/{id} | server.js:32-43
4. PATCH:/api/items/{id} | PATCH /api/items/{id} | server.js:45-54
5. DELETE:/api/items/{id} | DELETE /api/items/{id} | server.js:56-65
6. HEAD:/api/health | HEAD /api/health | server.js:67-70
7. OPTIONS:/api/health | OPTIONS /api/health | server.js:72-75

## Function Implementation Blocks

### GET:/api/items

```text
function getItems(req, res) {
  sendJson(res, 200, { route: 'GET /api/items', total: items.length, items: snapshotItems() });
}
```

### POST:/api/items

```text
function createItem(req, res) {
  const id = String(items.length + 1);
  items.push({ id, name: `item-${id}`, status: 'created' });
  sendJson(res, 201, { route: 'POST /api/items', total: items.length });
}
```

### PUT:/api/items/{id}

```text
function replaceItem(req, res) {
  const item = findItem('1');
  if (item) {
    item.name = `${item.name}-v2`;
    item.status = 'replaced';
    sendJson(res, 200, { route: 'PUT /api/items/:id', item });
    return;
  }

  items.push({ id: '1', name: 'item-1', status: 'inserted' });
  sendJson(res, 200, { route: 'PUT /api/items/:id', inserted: true, total: items.length });
}
```

### PATCH:/api/items/{id}

```text
function patchItem(req, res) {
  const item = findItem('1');
  if (!item) {
    sendJson(res, 404, { route: 'PATCH /api/items/:id', missing: true });
    return;
  }

  item.status = 'patched';
  sendJson(res, 200, { route: 'PATCH /api/items/:id', item });
}
```

### DELETE:/api/items/{id}

```text
function deleteItem(req, res) {
  const index = items.findIndex((item) => item.id === '1');
  if (index >= 0) {
    const removed = items.splice(index, 1)[0];
    sendJson(res, 200, { route: 'DELETE /api/items/:id', removed, total: items.length });
    return;
  }

  sendJson(res, 404, { route: 'DELETE /api/items/:id', removed: false });
}
```

### HEAD:/api/health

```text
function healthHead(req, res) {
  res.setHeader('X-Sample-Items', String(items.length));
  res.end();
}
```

### OPTIONS:/api/health

```text
function healthOptions(req, res) {
  res.setHeader('Allow', 'GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS');
  sendJson(res, 200, { route: 'OPTIONS /api/health', total: items.length });
}
```

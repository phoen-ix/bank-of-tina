def test_health_returns_ok(client, app):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'


def test_health_json_format(client, app):
    response = client.get('/health')
    assert response.content_type.startswith('application/json')
    data = response.get_json()
    assert 'status' in data

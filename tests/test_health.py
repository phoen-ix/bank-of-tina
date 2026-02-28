def test_health_returns_ok(client, app):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
    assert 'checks' in data
    assert data['checks']['database'] == 'ok'
    assert 'scheduler' in data['checks']
    assert 'icons_writable' in data['checks']


def test_health_json_format(client, app):
    response = client.get('/health')
    assert response.content_type.startswith('application/json')
    data = response.get_json()
    assert 'status' in data
    assert 'checks' in data

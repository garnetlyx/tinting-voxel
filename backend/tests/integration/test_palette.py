"""
Integration tests for /api/palettes/ endpoints.
"""


class TestListPalettes:
    """Tests for GET /api/palettes/."""

    def test_list_all_palettes(self, client):
        """List all palettes returns non-empty list."""
        response = client.get("/api/palettes/")
        assert response.status_code == 200
        data = response.json()
        assert "palettes" in data
        assert "categories" in data
        assert len(data["palettes"]) >= 10
        assert "standard" in data["categories"]

    def test_filter_by_category(self, client):
        """Filter palettes by category."""
        response = client.get("/api/palettes/?category=standard")
        assert response.status_code == 200
        data = response.json()
        assert len(data["palettes"]) >= 2
        for p in data["palettes"]:
            assert p["category"] == "standard"

    def test_filter_by_artistic_category(self, client):
        """Filter palettes by artistic category."""
        response = client.get("/api/palettes/?category=artistic")
        assert response.status_code == 200
        data = response.json()
        assert len(data["palettes"]) >= 1
        for p in data["palettes"]:
            assert p["category"] == "artistic"

    def test_invalid_category_returns_400(self, client):
        """Invalid category returns 400."""
        response = client.get("/api/palettes/?category=nonexistent")
        assert response.status_code == 400

    def test_palette_has_required_fields(self, client):
        """Each palette has id, name, description, category, colors."""
        response = client.get("/api/palettes/")
        data = response.json()
        for p in data["palettes"]:
            assert "id" in p
            assert "name" in p
            assert "description" in p
            assert "category" in p
            assert "colors" in p
            assert len(p["colors"]) >= 4

    def test_palette_color_has_required_fields(self, client):
        """Each color has name, hex, transmission_distance."""
        response = client.get("/api/palettes/")
        data = response.json()
        for p in data["palettes"]:
            for c in p["colors"]:
                assert "name" in c
                assert "hex" in c
                assert "transmission_distance" in c


class TestGetPalette:
    """Tests for GET /api/palettes/{palette_id}."""

    def test_get_existing_palette(self, client):
        """Get a known palette by ID."""
        response = client.get("/api/palettes/bambu_cmyk")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "bambu_cmyk"
        assert data["name"] == "Bambu CMYK"
        assert len(data["colors"]) == 4

    def test_get_nonexistent_palette(self, client):
        """Get a non-existent palette returns 404."""
        response = client.get("/api/palettes/nonexistent")
        assert response.status_code == 404

    def test_get_earth_tones_palette(self, client):
        """Get earth_tones palette has correct category."""
        response = client.get("/api/palettes/earth_tones")
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "artistic"
        assert len(data["colors"]) == 4

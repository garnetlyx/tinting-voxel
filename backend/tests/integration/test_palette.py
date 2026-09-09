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
        assert [p["id"] for p in data["palettes"]] == ["bambu_cmyw_phase6", "clear_cmywg"]


    def test_palette_has_required_fields(self, client):
        """Each palette has id, name, description, colors."""
        response = client.get("/api/palettes/")
        data = response.json()
        for p in data["palettes"]:
            assert "id" in p
            assert "name" in p
            assert "description" in p
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
        response = client.get("/api/palettes/bambu_cmyw_phase6")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "bambu_cmyw_phase6"
        assert data["name"] == "Bambu CMYW Phase 6"
        assert len(data["colors"]) == 4

    def test_get_nonexistent_palette(self, client):
        """Get a non-existent palette returns 404."""
        response = client.get("/api/palettes/nonexistent")
        assert response.status_code == 404

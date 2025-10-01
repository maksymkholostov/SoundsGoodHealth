from flask import Blueprint, jsonify


def init_id_mappings_routes() -> Blueprint:
    """Provide a stub ID mappings endpoint to satisfy frontend requests."""
    bp = Blueprint('id_mappings_api', __name__, url_prefix='/api')

    @bp.get('/id-mappings')
    def get_id_mappings():
        # Return empty mappings structure; extend later if needed
        return jsonify({"success": True, "mappings": {}})

    return bp



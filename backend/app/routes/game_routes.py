# backend/app/routes/game_routes.py
"""
Routes for all game-related pages.
"""
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, current_app
from flask_login import login_required, current_user
import json
import traceback
import os

# Create a new blueprint for games
game_bp = Blueprint('games', __name__, 
                   template_folder='../../../frontend/templates', 
                   static_folder='../../../frontend/static')

# --- Game Routes ---

@game_bp.route('/games')
@login_required
def games_page():
    """Serve the games selection page."""
    return render_template('games.html')

@game_bp.route('/game1')
@login_required
def game1_page():
    """Serve the original play game (renamed to game1.html)."""
    return render_template('game1.html')

@game_bp.route('/game2')
@login_required
def game2_page():
    """Serve the sound classification game page (Game 2)."""
    return render_template('game2.html')

def init_game_routes():
    """
    Initialize game routes.
    
    Returns:
        Configured Blueprint
    """
    return game_bp


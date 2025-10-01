#!/usr/bin/env python3
"""Check RF model parameters and size."""

import pickle
import numpy as np

# Load the RF model
model_path = 'backend/data/models/dict_ehoo/rf_dict_ehoo_ronrubin_20250806_064820002/rf_v01.pkl'
with open(model_path, 'rb') as f:
    rf_model = pickle.load(f)

print("=" * 80)
print("RANDOM FOREST MODEL ANALYSIS")
print("=" * 80)

# Basic info
print(f"Number of trees: {rf_model.n_estimators}")
print(f"Max depth: {rf_model.max_depth}")
print(f"Number of features: {rf_model.n_features_in_}")
print(f"Classes: {rf_model.classes_}")

# Count parameters per tree
total_nodes = 0
total_leaf_nodes = 0
total_parameters = 0

for i, tree in enumerate(rf_model.estimators_):
    tree_obj = tree.tree_
    n_nodes = tree_obj.node_count
    n_leaves = tree_obj.n_leaves
    total_nodes += n_nodes
    total_leaf_nodes += n_leaves
    
    # Each internal node stores: feature index, threshold, left/right child indices
    # Each leaf node stores: class probabilities
    internal_nodes = n_nodes - n_leaves
    params_per_tree = internal_nodes * 2  # feature + threshold for splits
    params_per_tree += n_leaves * len(rf_model.classes_)  # class probabilities at leaves
    total_parameters += params_per_tree
    
    if i < 5:  # Show first 5 trees
        print(f"  Tree {i}: {n_nodes} nodes, {n_leaves} leaves")

print(f"\nTotal nodes across all trees: {total_nodes:,}")
print(f"Total leaf nodes: {total_leaf_nodes:,}")
print(f"Approximate total parameters: {total_parameters:,}")

# Memory size
import os
model_size = os.path.getsize(model_path)
print(f"\nModel file size: {model_size:,} bytes ({model_size/1024:.1f} KB)")

# Feature importance
print(f"\nFeature importances shape: {rf_model.feature_importances_.shape}")
print(f"Non-zero important features: {np.sum(rf_model.feature_importances_ > 0)}")
print(f"Top 10 feature importance values: {np.sort(rf_model.feature_importances_)[-10:]}")

# Training samples used
if hasattr(rf_model, '_n_samples'):
    print(f"\nTraining samples seen: {rf_model._n_samples}")
print(f"Max samples per tree: {rf_model.max_samples if rf_model.max_samples else 'All (bootstrap)'}")

# Comparison
print("\n" + "=" * 80)
print("COMPARISON")
print("=" * 80)
print(f"CNN parameters: ~8,219,522")
print(f"RF parameters: ~{total_parameters:,}")
print(f"Ratio (CNN/RF): {8219522/total_parameters:.1f}x more parameters in CNN")
print(f"\nParameters per training sample (7 samples):")
print(f"  CNN: {8219522/7:,.0f} parameters/sample")
print(f"  RF: {total_parameters/7:,.0f} parameters/sample")
"""
Training analyzer for model performance assessment and visualization.

This module provides tools for analyzing model training metrics,
generating visualizations, and comparing different models.
"""
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from io import BytesIO
import base64
from typing import Dict, List, Any, Tuple, Optional
import json
import logging
from sklearn.metrics import confusion_matrix, classification_report
import pandas as pd
import seaborn as sns

logger = logging.getLogger(__name__)

class TrainingAnalyzer:
    """
    Analyzer for ML model training, providing performance metrics and visualizations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the TrainingAnalyzer.
        
        Args:
            config: Configuration parameters for analysis
        """
        self.config = config or {}
    
    def analyze_training_history(self, history_data: Dict[str, List[float]]) -> Dict[str, Any]:
        """
        Analyze training history data (e.g., from model.fit()).
        
        Args:
            history_data: Dictionary containing training metrics by epoch
            
        Returns:
            Dictionary containing analysis results
        """
        results = {
            "metrics": {},
            "convergence_analysis": {}
        }
        
        # For each metric, compute statistics and convergence info
        for metric_name, values in history_data.items():
            if len(values) == 0:
                continue
            
            # Basic statistics
            metric_stats = {
                "min": float(min(values)),
                "max": float(max(values)),
                "mean": float(np.mean(values)),
                "final": float(values[-1]),
                "values": [float(v) for v in values]
            }
            
            # Convergence analysis
            if len(values) >= 3:
                # Check if metric has leveled off
                window_size = min(5, len(values) // 3)  # Use 1/3 of epochs with max of 5
                recent_values = values[-window_size:]
                recent_change = abs(recent_values[-1] - recent_values[0])
                overall_change = abs(values[-1] - values[0])
                converged = recent_change < 0.01 * overall_change
                
                # Calculate slope of recent epochs
                epochs = list(range(len(values) - window_size, len(values)))
                slope = np.polyfit(epochs, recent_values, 1)[0]
                
                convergence = {
                    "converged": converged,
                    "recent_epochs_slope": float(slope),
                    "recent_epochs_change": float(recent_change),
                    "overall_change": float(overall_change)
                }
                
                results["convergence_analysis"][metric_name] = convergence
            
            results["metrics"][metric_name] = metric_stats
        
        # Overall assessment
        results["epochs"] = len(list(history_data.values())[0]) if history_data else 0
        results["likely_converged"] = all(
            info.get("converged", False) 
            for info in results["convergence_analysis"].values()
        ) if results["convergence_analysis"] else False
        
        return results
    
    def generate_training_curve_image(self, 
                                    history_data: Dict[str, List[float]],
                                    width: int = 800, 
                                    height: int = 400) -> Optional[str]:
        """
        Generate a visualization of training metrics over epochs.
        
        Args:
            history_data: Dictionary containing training metrics by epoch
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            Base64-encoded PNG image or None if generation fails
        """
        try:
            # Create a figure with two subplots: one for loss metrics, one for accuracy
            fig = Figure(figsize=(width/100, height/100), dpi=100)
            
            # Group metrics into loss and accuracy
            loss_metrics = [m for m in history_data.keys() if 'loss' in m.lower()]
            acc_metrics = [m for m in history_data.keys() if 'acc' in m.lower() or 'accuracy' in m.lower()]
            other_metrics = [m for m in history_data.keys() 
                           if m not in loss_metrics and m not in acc_metrics]
            
            num_plots = sum(1 for metrics in [loss_metrics, acc_metrics, other_metrics] if metrics)
            
            plot_idx = 0
            for metrics, title, ylabel in [
                (loss_metrics, 'Loss Metrics', 'Loss'),
                (acc_metrics, 'Accuracy Metrics', 'Accuracy'),
                (other_metrics, 'Other Metrics', 'Value')
            ]:
                if not metrics:
                    continue
                
                plot_idx += 1
                ax = fig.add_subplot(num_plots, 1, plot_idx)
                
                for metric in metrics:
                    epochs = range(1, len(history_data[metric]) + 1)
                    ax.plot(epochs, history_data[metric], label=metric)
                
                ax.set_title(title)
                ax.set_xlabel('Epoch')
                ax.set_ylabel(ylabel)
                ax.legend()
                ax.grid(True)
            
            fig.tight_layout()
            
            # Convert to base64 image
            buf = BytesIO()
            fig.savefig(buf, format='png')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            plt.close(fig)
            
            return img_base64
            
        except Exception as e:
            logger.error(f"Error generating training curve: {str(e)}")
            return None
    
    def generate_confusion_matrix_image(self,
                                      y_true: List[Any],
                                      y_pred: List[Any],
                                      class_names: Optional[List[str]] = None,
                                      width: int = 800,
                                      height: int = 800) -> Optional[str]:
        """
        Generate a confusion matrix visualization.
        
        Args:
            y_true: List of true labels
            y_pred: List of predicted labels
            class_names: List of class names
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            Base64-encoded PNG image or None if generation fails
        """
        try:
            # Compute confusion matrix
            cm = confusion_matrix(y_true, y_pred)
            
            # Normalize confusion matrix
            cm_normalized = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
            
            # Create figure
            fig = Figure(figsize=(width/100, height/100), dpi=100)
            ax = fig.add_subplot(1, 1, 1)
            
            # Plot confusion matrix as heatmap
            sns.heatmap(
                cm_normalized, 
                annot=cm,  # Show raw counts in cells
                fmt='d', 
                cmap='Blues',
                xticklabels=class_names if class_names else 'auto',
                yticklabels=class_names if class_names else 'auto',
                ax=ax
            )
            
            ax.set_title('Confusion Matrix')
            ax.set_xlabel('Predicted')
            ax.set_ylabel('True')
            
            fig.tight_layout()
            
            # Convert to base64 image
            buf = BytesIO()
            fig.savefig(buf, format='png')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            plt.close(fig)
            
            return img_base64
            
        except Exception as e:
            logger.error(f"Error generating confusion matrix: {str(e)}")
            return None
    
    def calculate_classification_metrics(self,
                                       y_true: List[Any],
                                       y_pred: List[Any],
                                       class_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Calculate detailed classification metrics.
        
        Args:
            y_true: List of true labels
            y_pred: List of predicted labels
            class_names: List of class names
            
        Returns:
            Dictionary containing classification metrics
        """
        try:
            # Get classification report as dictionary
            report = classification_report(y_true, y_pred, output_dict=True, 
                                         target_names=class_names if class_names else None)
            
            # Convert numpy values to Python native types
            for class_name, metrics in report.items():
                if isinstance(metrics, dict):
                    for metric_name, value in metrics.items():
                        report[class_name][metric_name] = float(value)
            
            # Calculate confusion matrix
            cm = confusion_matrix(y_true, y_pred).tolist()
            
            # Calculate overall accuracy
            accuracy = float(np.mean(np.array(y_true) == np.array(y_pred)))
            
            return {
                "classification_report": report,
                "confusion_matrix": cm,
                "accuracy": accuracy,
                "class_names": class_names if class_names else sorted(list(set(y_true + y_pred)))
            }
            
        except Exception as e:
            logger.error(f"Error calculating classification metrics: {str(e)}")
            return {"error": str(e)}
    
    def compare_models(self, 
                     model_results: List[Dict[str, Any]],
                     metric_name: str = "accuracy") -> Dict[str, Any]:
        """
        Compare multiple models based on a specific metric.
        
        Args:
            model_results: List of dictionaries containing model results
            metric_name: Metric to use for comparison
            
        Returns:
            Dictionary containing comparison results
        """
        try:
            comparison = []
            
            for model in model_results:
                model_name = model.get("model_name", "Unknown")
                
                # Check where the metric might be located in the result dict
                metric_value = None
                
                # 1. Check top level
                if metric_name in model:
                    metric_value = model[metric_name]
                
                # 2. Check if it's in the 'metrics' dict
                elif "metrics" in model and metric_name in model["metrics"]:
                    metric_value = model["metrics"][metric_name]
                
                # 3. Check if it's in classification_report.macro avg or weighted avg
                elif "classification_report" in model:
                    for avg_type in ["macro avg", "weighted avg"]:
                        if avg_type in model["classification_report"]:
                            if metric_name in model["classification_report"][avg_type]:
                                metric_value = model["classification_report"][avg_type][metric_name]
                                break
                
                # If we found the metric, add it to comparison
                if metric_value is not None:
                    comparison.append({
                        "model_name": model_name,
                        f"{metric_name}": float(metric_value)
                    })
            
            # Sort by the metric (descending)
            comparison.sort(key=lambda x: x[metric_name], reverse=True)
            
            return {
                "metric": metric_name,
                "models": comparison,
                "best_model": comparison[0]["model_name"] if comparison else None
            }
            
        except Exception as e:
            logger.error(f"Error comparing models: {str(e)}")
            return {"error": str(e)}
    
    def generate_model_comparison_image(self,
                                      model_results: List[Dict[str, Any]],
                                      metrics: Optional[List[str]] = None,
                                      width: int = 800,
                                      height: int = 500) -> Optional[str]:
        """
        Generate a bar chart comparing multiple models on selected metrics.
        
        Args:
            model_results: List of dictionaries containing model results
            metrics: List of metrics to compare (defaults to accuracy, precision, recall, f1-score)
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            Base64-encoded PNG image or None if generation fails
        """
        try:
            if not metrics:
                metrics = ["accuracy", "precision", "recall", "f1-score"]
            
            # Extract model names and metric values
            model_names = []
            metric_values = {metric: [] for metric in metrics}
            
            for model in model_results:
                model_name = model.get("model_name", "Unknown")
                model_names.append(model_name)
                
                for metric in metrics:
                    # Try to find the metric in different locations
                    value = None
                    
                    # 1. Check top level
                    if metric in model:
                        value = model[metric]
                    
                    # 2. Check if it's in the 'metrics' dict
                    elif "metrics" in model and metric in model["metrics"]:
                        value = model["metrics"][metric]
                    
                    # 3. Check if it's in classification_report.weighted avg
                    elif "classification_report" in model and "weighted avg" in model["classification_report"]:
                        if metric in model["classification_report"]["weighted avg"]:
                            value = model["classification_report"]["weighted avg"][metric]
                    
                    # If we didn't find it, use NaN
                    metric_values[metric].append(float(value) if value is not None else np.nan)
            
            # Create figure
            fig = Figure(figsize=(width/100, height/100), dpi=100)
            ax = fig.add_subplot(1, 1, 1)
            
            # Set up bar positions
            num_models = len(model_names)
            num_metrics = len(metrics)
            bar_width = 0.8 / num_metrics
            index = np.arange(num_models)
            
            # Plot grouped bars
            for i, metric in enumerate(metrics):
                ax.bar(
                    index + i * bar_width - 0.4 + bar_width/2, 
                    metric_values[metric], 
                    bar_width, 
                    label=metric
                )
            
            # Customize plot
            ax.set_xlabel('Model')
            ax.set_ylabel('Score')
            ax.set_title('Model Comparison')
            ax.set_xticks(index)
            ax.set_xticklabels(model_names, rotation=45, ha='right')
            ax.legend()
            ax.grid(axis='y')
            
            # Set y-axis to start at 0 and end at a little above the max value
            max_value = max(max(values) for values in metric_values.values() if values)
            ax.set_ylim(0, min(1.0, max_value * 1.1))  # Cap at 1.0 for accuracy metrics
            
            fig.tight_layout()
            
            # Convert to base64 image
            buf = BytesIO()
            fig.savefig(buf, format='png')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
            plt.close(fig)
            
            return img_base64
            
        except Exception as e:
            logger.error(f"Error generating model comparison: {str(e)}")
            return None
    
    # DB-OPERATION: create unknown
    def save_analysis_results(self, 
                            results: Dict[str, Any], 
                            output_path: str) -> bool:
        """
        Save analysis results to a JSON file.
        
        Args:
            results: Analysis results dictionary
            output_path: Path to save the results
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w') as f:
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                json.dump(results, f, indent=2)
            
            return True
        
        except Exception as e:
            logger.error(f"Error saving analysis results: {str(e)}")
            return False

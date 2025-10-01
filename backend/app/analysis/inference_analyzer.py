"""
Analysis service for coordinating data analysis components.

This service provides methods for analyzing recordings, training metrics,
and inference results, managing the storage of analysis data and coordinating
with the relevant analyzer components.
"""
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from app.analysis.recording_analyzer import RecordingAnalyzer
from app.analysis.training_analyzer import TrainingAnalyzer
from app.analysis.inference_analyzer import InferenceAnalyzer
from app.storage.file_manager import FileManager
from app.core.repositories.recording_repo import RecordingRepository
from app.core.repositories.model_repo import ModelRepository

logger = logging.getLogger(__name__)

class AnalysisService:
    """
    Service for coordinating data analysis operations.
    
    This service handles the analysis of recordings, training metrics,
    and inference results, managing the storage of analysis data and
    providing a unified interface for analysis operations.
    """
    
    def __init__(self,
                file_manager: FileManager,
                recording_repo: RecordingRepository,
                model_repo: ModelRepository,
                config: Optional[Dict[str, Any]] = None):
        """
        Initialize the AnalysisService.
        
        Args:
            file_manager: File manager for handling file operations
            recording_repo: Repository for recording data
            model_repo: Repository for model data
            config: Configuration parameters
        """
        self.file_manager = file_manager
        self.recording_repo = recording_repo
        self.model_repo = model_repo
        self.config = config or {}
        
        # Initialize analyzers
        self.recording_analyzer = RecordingAnalyzer(config)
        self.training_analyzer = TrainingAnalyzer(config)
        self.inference_analyzer = InferenceAnalyzer(config)
        
        # Analysis storage paths
        self.analysis_base_dir = os.path.join(
            self.file_manager.get_data_dir(), 'analysis'
        )
        os.makedirs(self.analysis_base_dir, exist_ok=True)
        
        # Create subdirectories for each analysis type
        for subdir in ['recordings', 'training', 'inference']:
            os.makedirs(os.path.join(self.analysis_base_dir, subdir), exist_ok=True)
    
    def analyze_recording(self, 
                        user_id: str, 
                        dictionary_id: str, 
                        recording_id: str,
                        include_visualizations: bool = True) -> Dict[str, Any]:
        """
        Analyze a single recording.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            recording_id: Recording ID
            include_visualizations: Whether to include waveform and spectrogram visualizations
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            # Get recording path
            recording_path = self.recording_repo.get_recording_path(
                user_id, dictionary_id, recording_id
            )
            
            if not os.path.exists(recording_path):
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                return {
                    "error": f"Recording not found: {recording_id}"
                }
            
            # Perform analysis
            analysis = self.recording_analyzer.analyze_recording(recording_path)
            
            # Add visualizations if requested
            if include_visualizations:
                analysis["waveform_image"] = self.recording_analyzer.generate_waveform_image(
                    recording_path
                )
                analysis["spectrogram_image"] = self.recording_analyzer.generate_spectrogram_image(
                    recording_path
                )
            
            # Add metadata
            analysis["user_id"] = user_id
            analysis["dictionary_id"] = dictionary_id
            analysis["recording_id"] = recording_id
            analysis["timestamp"] = datetime.now().isoformat()
            
            # Save analysis
            self._save_recording_analysis(
                user_id, dictionary_id, recording_id, analysis
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing recording {recording_id}: {str(e)}")
            return {"error": str(e)}
    
    def analyze_dictionary_recordings(self,
                                    user_id: str,
                                    dictionary_id: str,
                                    recording_type: str = 'gold',
                                    include_visualizations: bool = False) -> Dict[str, Any]:
        """
        Analyze all recordings in a dictionary.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            recording_type: Type of recordings to analyze ('gold', 'raw', or 'augmented')
            include_visualizations: Whether to include visualizations
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            # Get directory for recordings
            base_data_dir = self.file_manager.get_data_dir()
            
            if recording_type == 'raw':
                recordings_dir = os.path.join(
                    base_data_dir, 'raw', user_id, dictionary_id
                )
            else:  # 'gold' or 'augmented'
                recordings_dir = os.path.join(
                    base_data_dir, 'processed', user_id, dictionary_id, recording_type
                )
            
            if not os.path.exists(recordings_dir):
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                return {
                    "error": f"Recordings directory not found: {recordings_dir}"
                }
            
            # Analyze directory
            analysis = self.recording_analyzer.analyze_recordings_in_directory(
                recordings_dir, include_visualizations
            )
            
            # Add metadata
            analysis["user_id"] = user_id
            analysis["dictionary_id"] = dictionary_id
            analysis["recording_type"] = recording_type
            analysis["timestamp"] = datetime.now().isoformat()
            
            # Save analysis
            self._save_dictionary_recording_analysis(
                user_id, dictionary_id, recording_type, analysis
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing dictionary recordings: {str(e)}")
            return {"error": str(e)}
    
    def analyze_training_history(self,
                               user_id: str,
                               dictionary_id: str,
                               model_id: str,
                               history_data: Dict[str, List[float]]) -> Dict[str, Any]:
        """
        Analyze training history data.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            model_id: Model ID
            history_data: Dictionary containing training metrics by epoch
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            # Perform analysis
            analysis = self.training_analyzer.analyze_training_history(history_data)
            
            # Generate training curve visualization
            training_curve = self.training_analyzer.generate_training_curve_image(
                history_data
            )
            
            if training_curve:
                analysis["training_curve_image"] = training_curve
            
            # Add metadata
            analysis["user_id"] = user_id
            analysis["dictionary_id"] = dictionary_id
            analysis["model_id"] = model_id
            analysis["timestamp"] = datetime.now().isoformat()
            
            # Save analysis
            self._save_training_analysis(
                user_id, dictionary_id, model_id, analysis
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing training history: {str(e)}")
            return {"error": str(e)}
    
    def analyze_model_performance(self,
                                user_id: str,
                                dictionary_id: str,
                                model_id: str,
                                y_true: List[Any],
                                y_pred: List[Any],
                                class_names: List[str]) -> Dict[str, Any]:
        """
        Analyze model performance based on predictions.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            model_id: Model ID
            y_true: List of true labels
            y_pred: List of predicted labels
            class_names: List of class names
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            # Calculate classification metrics
            metrics = self.training_analyzer.calculate_classification_metrics(
                y_true, y_pred, class_names
            )
            
            # Generate confusion matrix visualization
            confusion_matrix = self.training_analyzer.generate_confusion_matrix_image(
                y_true, y_pred, class_names
            )
            
            if confusion_matrix:
                metrics["confusion_matrix_image"] = confusion_matrix
            
            # Add metadata
            metrics["user_id"] = user_id
            metrics["dictionary_id"] = dictionary_id
            metrics["model_id"] = model_id
            metrics["timestamp"] = datetime.now().isoformat()
            
            # Save analysis
            self._save_model_performance_analysis(
                user_id, dictionary_id, model_id, metrics
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error analyzing model performance: {str(e)}")
            return {"error": str(e)}
    
    def compare_models(self,
                     user_id: str,
                     dictionary_id: str,
                     model_ids: List[str],
                     metric: str = "accuracy") -> Dict[str, Any]:
        """
        Compare multiple models based on their performance.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            model_ids: List of model IDs to compare
            metric: Metric to use for comparison
            
        Returns:
            Dictionary containing comparison results
        """
        try:
            # Load performance analysis for each model
            model_results = []
            
            for model_id in model_ids:
                analysis_path = os.path.join(
                    self.analysis_base_dir,
                    'training',
                    user_id,
                    dictionary_id,
                    f"{model_id}_performance.json"
                )
                
                if os.path.exists(analysis_path):
                # STORAGE-OPERATION: Will be replaced by DatabaseManager
                    with open(analysis_path, 'r') as f:
                    # STORAGE-OPERATION: Will be replaced by DatabaseManager
                        analysis = json.load(f)
                        analysis["model_name"] = model_id
                        model_results.append(analysis)
            
            if not model_results:
                return {
                    "error": "No model performance data found"
                }
            
            # Compare models
            comparison = self.training_analyzer.compare_models(
                model_results, metric
            )
            
            # Generate comparison visualization
            comparison_image = self.training_analyzer.generate_model_comparison_image(
                model_results
            )
            
            if comparison_image:
                comparison["comparison_image"] = comparison_image
            
            # Add metadata
            comparison["user_id"] = user_id
            comparison["dictionary_id"] = dictionary_id
            comparison["model_ids"] = model_ids
            comparison["timestamp"] = datetime.now().isoformat()
            
            # Save comparison
            self._save_model_comparison(
                user_id, dictionary_id, comparison
            )
            
            return comparison
            
        except Exception as e:
            logger.error(f"Error comparing models: {str(e)}")
            return {"error": str(e)}
    
    def analyze_inference_session(self,
                                user_id: str,
                                dictionary_id: str,
                                model_id: str,
                                session_id: str,
                                inference_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze results from an inference session.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            model_id: Model ID
            session_id: Session ID
            inference_results: List of dictionaries containing inference results
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            # Perform analysis
            analysis = self.inference_analyzer.analyze_inference_session(inference_results)
            
            # Generate confusion matrix if ground truth is available
            if analysis.get("accuracy_analysis"):
                # Extract true and predicted labels
                y_true = []
                y_pred = []
                
                for result in inference_results:
                    if "ground_truth" in result:
                        y_true.append(result["ground_truth"])
                        y_pred.append(result.get("prediction", "unknown"))
                
                if y_true:
                    class_names = sorted(list(set(y_true + y_pred)))
                    
                    confusion_matrix = self.inference_analyzer.generate_confusion_heatmap(
                        inference_results
                    )
                    
                    if confusion_matrix:
                        analysis["confusion_matrix_image"] = confusion_matrix
            
            # Add metadata
            analysis["user_id"] = user_id
            analysis["dictionary_id"] = dictionary_id
            analysis["model_id"] = model_id
            analysis["session_id"] = session_id
            analysis["timestamp"] = datetime.now().isoformat()
            
            # Save analysis
            self._save_inference_session_analysis(
                user_id, dictionary_id, model_id, session_id, analysis
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing inference session: {str(e)}")
            return {"error": str(e)}
    
    def analyze_user_progress(self,
                            user_id: str,
                            dictionary_id: str,
                            metric: str = "overall_accuracy") -> Dict[str, Any]:
        """
        Analyze user progress across multiple inference sessions.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            metric: Metric to track progress for
            
        Returns:
            Dictionary containing progress analysis
        """
        try:
            # Find all inference session analyses for the user/dictionary
            sessions_dir = os.path.join(
                self.analysis_base_dir,
                'inference',
                user_id,
                dictionary_id
            )
            
            if not os.path.exists(sessions_dir):
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                return {
                    "error": f"No inference sessions found for user {user_id}, dictionary {dictionary_id}"
                }
            
            # Collect session data
            sessions = []
            
            for filename in os.listdir(sessions_dir):
                if filename.endswith('_session.json'):
                    file_path = os.path.join(sessions_dir, filename)
                    
                    with open(file_path, 'r') as f:
                    # STORAGE-OPERATION: Will be replaced by DatabaseManager
                        session_data = json.load(f)
                        sessions.append(session_data)
            
            if not sessions:
                return {
                    "error": f"No inference sessions found for user {user_id}, dictionary {dictionary_id}"
                }
            
            # Analyze progress
            progress = self.inference_analyzer.analyze_user_progress(
                sessions, [metric]
            )
            
            # Generate progress chart
            progress_chart = self.inference_analyzer.generate_progress_chart(
                sessions, metric
            )
            
            if progress_chart:
                progress["progress_chart_image"] = progress_chart
            
            # Add metadata
            progress["user_id"] = user_id
            progress["dictionary_id"] = dictionary_id
            progress["metric"] = metric
            progress["timestamp"] = datetime.now().isoformat()
            
            # Save progress analysis
            self._save_user_progress_analysis(
                user_id, dictionary_id, progress
            )
            
            return progress
            
        except Exception as e:
            logger.error(f"Error analyzing user progress: {str(e)}")
            return {"error": str(e)}
    
    def detect_error_patterns(self,
                            user_id: str,
                            dictionary_id: str,
                            model_id: Optional[str] = None,
                            session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Detect patterns in incorrect predictions.
        
        Args:
            user_id: User ID
            dictionary_id: Dictionary ID
            model_id: Model ID (optional, if None use all models)
            session_id: Session ID (optional, if None use all sessions)
            
        Returns:
            Dictionary containing error pattern analysis
        """
        try:
            # Find relevant inference results
            inference_results = []
            
            # Base directory for inference sessions
            sessions_dir = os.path.join(
                self.analysis_base_dir,
                'inference',
                user_id,
                dictionary_id
            )
            
            if not os.path.exists(sessions_dir):
            # STORAGE-OPERATION: Will be replaced by DatabaseManager
                return {
                    "error": f"No inference sessions found for user {user_id}, dictionary {dictionary_id}"
                }
            
            # Function to extract results from a session file
            def extract_results(file_path):
                with open(file_path, 'r') as f:
                # STORAGE-OPERATION: Will be replaced by DatabaseManager
                    session_data = json.load(f)
                    # Check if raw inference results are stored
                    if "raw_results" in session_data:
                        return session_data["raw_results"]
                    return []
            
            # Collect inference results
            if session_id:
                # Specific session
                if model_id:
                    # Specific model and session
                    file_path = os.path.join(
                        sessions_dir,
                        f"{model_id}_{session_id}_session.json"
                    )
                    if os.path.exists(file_path):
                    # STORAGE-OPERATION: Will be replaced by DatabaseManager
                        inference_results.extend(extract_results(file_path))
                else:
                    # Any model, specific session
                    for filename in os.listdir(sessions_dir):
                        if filename.endswith(f"_{session_id}_session.json"):
                            file_path = os.path.join(sessions_dir, filename)
                            inference_results.extend(extract_results(file_path))
            else:
                # All sessions
                if model_id:
                    # Specific model, all sessions
                    for filename in os.listdir(sessions_dir):
                        if filename.startswith(f"{model_id}_") and filename.endswith("_session.json"):
                            file_path = os.path.join(sessions_dir, filename)
                            inference_results.extend(extract_results(file_path))
                else:
                    # All models, all sessions
                    for filename in os.listdir(sessions_dir):
                        if filename.endswith("_session.json"):
                            file_path = os.path.join(sessions_dir, filename)
                            inference_results.extend(extract_results(file_path))
            
            if not inference_results:
                return {
                    "error": "No inference results found with ground truth data"
                }
            
            # Detect error patterns
            patterns = self.inference_analyzer.detect_error_patterns(inference_results)
            
            # Add metadata
            patterns["user_id"] = user_id
            patterns["dictionary_id"] = dictionary_id
            if model_id:
                patterns["model_id"] = model_id
            if session_id:
                patterns["session_id"] = session_id
            patterns["timestamp"] = datetime.now().isoformat()
            
            # Save analysis
            analysis_id = f"{model_id or 'all'}_{session_id or 'all'}"
            self._save_error_pattern_analysis(
                user_id, dictionary_id, analysis_id, patterns
            )
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting error patterns: {str(e)}")
            return {"error": str(e)}
    
    def _save_recording_analysis(self, 
                               user_id: str, 
                               dictionary_id: str, 
                               recording_id: str,
                               analysis: Dict[str, Any]) -> None:
        """Save recording analysis results."""
        output_dir = os.path.join(
            self.analysis_base_dir,
            'recordings',
            user_id,
            dictionary_id
        )
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f"{recording_id}_analysis.json")
        
        with open(output_path, 'w') as f:
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            json.dump(analysis, f, indent=2)
    
    def _save_dictionary_recording_analysis(self, 
                                          user_id: str, 
                                          dictionary_id: str, 
                                          recording_type: str,
                                          analysis: Dict[str, Any]) -> None:
        """Save dictionary recording analysis results."""
        output_dir = os.path.join(
            self.analysis_base_dir,
            'recordings',
            user_id,
            dictionary_id
        )
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f"{recording_type}_analysis.json")
        
        with open(output_path, 'w') as f:
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            json.dump(analysis, f, indent=2)
    
    def _save_training_analysis(self, 
                              user_id: str, 
                              dictionary_id: str, 
                              model_id: str,
                              analysis: Dict[str, Any]) -> None:
        """Save training analysis results."""
        output_dir = os.path.join(
            self.analysis_base_dir,
            'training',
            user_id,
            dictionary_id
        )
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f"{model_id}_training.json")
        
        with open(output_path, 'w') as f:
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            json.dump(analysis, f, indent=2)
    
    def _save_model_performance_analysis(self, 
                                       user_id: str, 
                                       dictionary_id: str, 
                                       model_id: str,
                                       analysis: Dict[str, Any]) -> None:
        """Save model performance analysis results."""
        output_dir = os.path.join(
            self.analysis_base_dir,
            'training',
            user_id,
            dictionary_id
        )
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f"{model_id}_performance.json")
        
        with open(output_path, 'w') as f:
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            json.dump(analysis, f, indent=2)
    
    def _save_model_comparison(self, 
                             user_id: str, 
                             dictionary_id: str, 
                             analysis: Dict[str, Any]) -> None:
        """Save model comparison results."""
        output_dir = os.path.join(
            self.analysis_base_dir,
            'training',
            user_id,
            dictionary_id
        )
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, "model_comparison.json")
        
        with open(output_path, 'w') as f:
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            json.dump(analysis, f, indent=2)
    
    def _save_inference_session_analysis(self, 
                                       user_id: str, 
                                       dictionary_id: str, 
                                       model_id: str,
                                       session_id: str,
                                       analysis: Dict[str, Any]) -> None:
        """Save inference session analysis results."""
        output_dir = os.path.join(
            self.analysis_base_dir,
            'inference',
            user_id,
            dictionary_id
        )
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f"{model_id}_{session_id}_session.json")
        
        with open(output_path, 'w') as f:
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            json.dump(analysis, f, indent=2)
    
    def _save_user_progress_analysis(self, 
                                   user_id: str, 
                                   dictionary_id: str, 
                                   analysis: Dict[str, Any]) -> None:
        """Save user progress analysis results."""
        output_dir = os.path.join(
            self.analysis_base_dir,
            'inference',
            user_id,
            dictionary_id
        )
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, "progress_analysis.json")
        
        with open(output_path, 'w') as f:
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            json.dump(analysis, f, indent=2)
    
    def _save_error_pattern_analysis(self, 
                                   user_id: str, 
                                   dictionary_id: str,
                                   analysis_id: str,
                                   analysis: Dict[str, Any]) -> None:
        """Save error pattern analysis results."""
        output_dir = os.path.join(
            self.analysis_base_dir,
            'inference',
            user_id,
            dictionary_id
        )
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f"{analysis_id}_errors.json")
        
        with open(output_path, 'w') as f:
        # STORAGE-OPERATION: Will be replaced by DatabaseManager
            json.dump(analysis, f, indent=2)
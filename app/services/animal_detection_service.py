"""
Servicio de Detección de Animales
Usa YOLOv8 (Ultralytics) para detección en tiempo real
"""
from ultralytics import YOLO
import cv2
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class AnimalDetectionService:
    """
    Servicio de detección de animales usando YOLOv8
    """
    
    def __init__(self):
        # Cargar modelo YOLOv8
        self.model = YOLO(settings.YOLO_MODEL)
        self.confidence_threshold = settings.ANIMAL_CONFIDENCE_THRESHOLD
        self.animal_classes = self._get_target_classes()
        
        logger.info(
            "Servicio de detección de animales inicializado",
            model=settings.YOLO_MODEL,
            confidence=self.confidence_threshold,
            target_classes=self.animal_classes
        )
    
    def _get_target_classes(self) -> List[int]:
        """
        Obtiene IDs de clases de animales a detectar
        COCO dataset: dog=0, cat=15, bird=19, horse=22, etc.
        """
        # Mapeo de nombres a IDs en COCO
        coco_animal_map = {
            "bird": 14,
            "cat": 15,
            "dog": 16,
            "horse": 17,
            "sheep": 18,
            "cow": 19,
            "elephant": 20,
            "bear": 21,
            "zebra": 22,
            "giraffe": 23,
        }
        
        target_ids = []
        for animal in settings.get_animal_classes:
            if animal in coco_animal_map:
                target_ids.append(coco_animal_map[animal])
        
        return target_ids
    
    def detect_animals(self, image: np.ndarray) -> List[Dict]:
        """
        Detecta animales en una imagen/frame
        Retorna lista de detecciones con bounding box y confianza
        """
        # Ejecutar inferencia YOLOv8
        results = self.model(
            image,
            conf=self.confidence_threshold,
            classes=self.animal_classes if self.animal_classes else None,
            verbose=False
        )
        
        detections = []
        
        for result in results:
            boxes = result.boxes
            
            if boxes is None:
                continue
            
            for box in boxes:
                # Extraer información
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0].cpu().numpy())
                class_id = int(box.cls[0].cpu().numpy())
                class_name = result.names[class_id]
                
                detection = {
                    "class": class_name,
                    "class_id": class_id,
                    "confidence": confidence,
                    "bbox": {
                        "x1": int(x1),
                        "y1": int(y1),
                        "x2": int(x2),
                        "y2": int(y2)
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                detections.append(detection)
        
        logger.debug(
            f"{len(detections)} animales detectados",
            detections=[d["class"] for d in detections]
        )
        
        return detections
    
    def has_animals(self, image: np.ndarray) -> bool:
        """
        Verifica si hay animales en la imagen
        """
        detections = self.detect_animals(image)
        return len(detections) > 0
    
    def get_animal_types(self, image: np.ndarray) -> List[str]:
        """
        Retorna lista de tipos de animales detectados
        """
        detections = self.detect_animals(image)
        return list(set([d["class"] for d in detections]))
    
    def draw_detections(
        self,
        image: np.ndarray,
        detections: List[Dict]
    ) -> np.ndarray:
        """
        Dibuja bounding boxes en la imagen
        """
        annotated_image = image.copy()
        
        for detection in detections:
            bbox = detection["bbox"]
            class_name = detection["class"]
            confidence = detection["confidence"]
            
            # Coordenadas
            x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
            
            # Dibujar bounding box
            cv2.rectangle(
                annotated_image,
                (x1, y1),
                (x2, y2),
                color=(0, 255, 0),  # Verde
                thickness=2
            )
            
            # Dibujar label
            label = f"{class_name}: {confidence:.2f}"
            cv2.putText(
                annotated_image,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )
        
        return annotated_image
    
    def process_video_stream(
        self,
        camera_index: int = 0,
        callback=None
    ):
        """
        Procesa stream de video en tiempo real
        callback se ejecuta cuando se detecta animal
        """
        cap = cv2.VideoCapture(camera_index)
        
        if not cap.isOpened():
            logger.error("No se pudo abrir la cámara")
            return
        
        logger.info("Iniciando detección de animales en tiempo real...")
        
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # Detectar animales cada 5 frames (optimización)
            if frame_count % 5 == 0:
                detections = self.detect_animals(frame)
                
                if len(detections) > 0:
                    logger.warning(
                        "Animal detectado",
                        animals=[d["class"] for d in detections]
                    )
                    
                    if callback:
                        callback(detections, frame)
                
                # Dibujar detecciones
                annotated_frame = self.draw_detections(frame, detections)
            else:
                annotated_frame = frame
            
            # Mostrar
            cv2.imshow("Detección de Animales", annotated_frame)
            
            # Salir con ESC
            if cv2.waitKey(1) & 0xFF == 27:
                break
            
            frame_count += 1
        
        cap.release()
        cv2.destroyAllWindows()
        logger.info("Detección de animales detenida")


# Instancia global del servicio
animal_service = AnimalDetectionService()
"""
Servicio de Reconocimiento Facial
Usa face_recognition (dlib) + OpenCV
Incluye detección de liveness (anti-spoofing)
"""
import cv2
import face_recognition
import numpy as np
from typing import List, Tuple, Optional, Dict
from datetime import datetime
import structlog

from app.core.config import settings
from app.core.security import biometric_cipher

logger = structlog.get_logger()


class FaceRecognitionService:
    """
    Servicio de reconocimiento facial con liveness detection
    """
    
    def __init__(self):
        self.tolerance = settings.FACE_RECOGNITION_TOLERANCE
        self.model = settings.FACE_DETECTION_MODEL
        self.liveness_enabled = settings.LIVENESS_ENABLED
        
        logger.info(
            "Servicio de reconocimiento facial inicializado",
            model=self.model,
            tolerance=self.tolerance,
            liveness=self.liveness_enabled
        )
    
    def detect_faces(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detecta rostros en una imagen
        Retorna lista de bounding boxes (top, right, bottom, left)
        """
        # Convertir BGR (OpenCV) a RGB (face_recognition)
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Detectar ubicaciones de rostros
        face_locations = face_recognition.face_locations(
            rgb_image,
            model=self.model
        )
        
        logger.debug(f"{len(face_locations)} rostros detectados")
        return face_locations
    
    def encode_face(self, image: np.ndarray, face_location: Tuple) -> Optional[np.ndarray]:
        """
        Genera encoding (plantilla biométrica) de un rostro
        """
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        encodings = face_recognition.face_encodings(
            rgb_image,
            known_face_locations=[face_location]
        )
        
        if len(encodings) == 0:
            logger.warning("No se pudo generar encoding del rostro")
            return None
        
        return encodings[0]
    
    def save_biometric_template(self, encoding: np.ndarray) -> str:
        """
        Encripta y guarda una plantilla biométrica
        Retorna el template encriptado como string
        """
        # Convertir numpy array a bytes
        template_bytes = encoding.tobytes()
        
        # Encriptar con AES-256
        encrypted_template = biometric_cipher.encrypt_biometric_template(template_bytes)
        
        logger.info("Plantilla biométrica encriptada y guardada")
        return encrypted_template
    
    def load_biometric_template(self, encrypted_template: str) -> Optional[np.ndarray]:
        """
        Carga y desencripta una plantilla biométrica
        """
        try:
            # Desencriptar
            template_bytes = biometric_cipher.decrypt_biometric_template(encrypted_template)
            
            # Convertir bytes a numpy array
            encoding = np.frombuffer(template_bytes, dtype=np.float64)
            
            return encoding
        except Exception as e:
            logger.error("Error cargando plantilla biométrica", error=str(e))
            return None
    
    def compare_faces(
        self,
        known_encoding: np.ndarray,
        unknown_encoding: np.ndarray,
        tolerance: Optional[float] = None
    ) -> bool:
        """
        Compara dos encodings faciales
        Retorna True si son la misma persona
        """
        if tolerance is None:
            tolerance = self.tolerance
        
        # Usar distancia euclidiana (face_recognition usa esto internamente)
        distance = np.linalg.norm(known_encoding - unknown_encoding)
        
        # Distancia menor = más similar
        is_match = distance < tolerance
        
        logger.debug(
            "Comparación facial",
            distance=round(distance, 4),
            tolerance=tolerance,
            match=is_match
        )
        
        return is_match
    
    def recognize_face(
        self,
        image: np.ndarray,
        known_encodings: List[np.ndarray],
        known_ids: List[str]
    ) -> Optional[Dict]:
        """
        Reconoce un rostro comparando con encodings conocidos
        Retorna información de la persona si hay match
        """
        # Detectar rostros
        face_locations = self.detect_faces(image)
        
        if len(face_locations) != 1:
            logger.warning("Se requiere exactamente un rostro", count=len(face_locations))
            return None
        
        # Asumir un solo rostro por ahora
        face_location = face_locations[0]
        
        # Generar encoding
        unknown_encoding = self.encode_face(image, face_location)
        
        if unknown_encoding is None:
            return None
        
        if not known_encodings or len(known_encodings) != len(known_ids):
            return None

        distances = face_recognition.face_distance(known_encodings, unknown_encoding)
        best_index = int(np.argmin(distances))
        best_distance = float(distances[best_index])
        if best_distance < self.tolerance:
            liveness = self.detect_liveness(image, face_location)
            if not liveness["is_live"]:
                logger.warning("Reconocimiento rechazado por liveness", reason=liveness.get("reason"))
                return None
            logger.info(
                "Reconocimiento exitoso",
                person_id=known_ids[best_index],
                distance=round(best_distance, 4),
            )
            return {
                "person_id": known_ids[best_index],
                "confidence": max(0.0, min(1.0, 1.0 - best_distance)),
                "distance": best_distance,
                "face_location": face_location,
                "liveness": liveness,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        logger.info("Rostro no reconocido")
        return None
    
    def detect_liveness(
        self,
        image: np.ndarray,
        face_location: Tuple
    ) -> Dict:
        """
        Detección de liveness (anti-spoofing)
        Verifica que sea una persona real y no una foto/video
        
        Implementa:
        - Detección de parpadeo
        - Análisis de movimiento 3D
        - Detección de textura de piel
        """
        if not self.liveness_enabled:
            return {"is_live": True, "method": "disabled"}
        
        # Una imagen aislada no puede demostrar parpadeo o movimiento. Aceptarla
        # como prueba de vida permitiría usar una fotografía. Se rechaza hasta
        # integrar una secuencia temporal o un sensor de profundidad real.
        logger.warning("Liveness no disponible para imagen única; acceso rechazado")
        return {
            "is_live": False,
            "reason": "temporal_liveness_required",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _detect_blink(self, face_roi: np.ndarray) -> float:
        """
        Detecta parpadeo analizando ojos
        Implementación simplificada - en producción usar modelo especializado
        """
        raise NotImplementedError("El parpadeo requiere una secuencia temporal")
    
    def _analyze_texture(self, face_roi: np.ndarray) -> float:
        """
        Analiza textura de piel para detectar pantallas/fotos
        """
        raise NotImplementedError("Se requiere un modelo anti-spoofing validado")
    
    def _analyze_depth(self, face_roi: np.ndarray) -> float:
        """
        Analiza profundidad (requiere cámara RGB-D o stereo)
        """
        raise NotImplementedError("Se requiere un sensor de profundidad")
    
    def capture_enrollment_images(
        self,
        camera_index: int = 0,
        num_images: int = 5
    ) -> Optional[List[np.ndarray]]:
        """
        Captura múltiples imágenes para enrollment
        Guía al usuario para girar la cabeza
        """
        cap = cv2.VideoCapture(camera_index)
        
        if not cap.isOpened():
            logger.error("No se pudo abrir la cámara")
            return None
        
        images = []
        positions = ["frontal", "left", "right", "up", "down"]
        
        print("\n=== ENROLLMENT FACIAL ===")
        print(f"Se capturarán {num_images} imágenes")
        print("Sigue las instrucciones en pantalla\n")
        
        for i, position in enumerate(positions[:num_images]):
            print(f"\nPosición {i+1}/{num_images}: {position}")
            print("Presiona ESPACIO para capturar, ESC para cancelar")
            
            # Esperar a que el usuario se posicione
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Mostrar frame con instrucciones
                cv2.putText(
                    frame,
                    f"Posicion: {position}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )
                
                cv2.imshow("Enrollment", frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == 32:  # Espacio
                    images.append(frame.copy())
                    print(f"✓ Imagen {i+1} capturada")
                    break
                elif key == 27:  # ESC
                    print("Enrollment cancelado")
                    cap.release()
                    cv2.destroyAllWindows()
                    return None
        
        cap.release()
        cv2.destroyAllWindows()
        
        logger.info(f"{len(images)} imágenes de enrollment capturadas")
        return images
    
    def generate_template_from_images(
        self,
        images: List[np.ndarray]
    ) -> Optional[np.ndarray]:
        """
        Genera una plantilla biométrica promedio desde múltiples imágenes
        """
        encodings = []
        
        for i, image in enumerate(images):
            face_locations = self.detect_faces(image)
            
            if len(face_locations) != 1:
                logger.warning("Imagen de enrollment inválida", image=i + 1, faces=len(face_locations))
                return None
            
            encoding = self.encode_face(image, face_locations[0])
            
            if encoding is not None:
                encodings.append(encoding)
        
        if len(encodings) != len(images):
            logger.error("No se pudieron generar encodings")
            return None
        
        # Promediar todos los encodings
        avg_encoding = np.mean(encodings, axis=0)
        if any(np.linalg.norm(encoding - avg_encoding) >= self.tolerance for encoding in encodings):
            logger.warning("Las imágenes de enrollment no corresponden consistentemente al mismo rostro")
            return None
        
        logger.info(
            "Plantilla biométrica generada",
            num_images=len(encodings),
            encoding_shape=avg_encoding.shape
        )
        
        return avg_encoding


# Instancia global del servicio
face_service = FaceRecognitionService()

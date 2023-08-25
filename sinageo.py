"""
Model exported as python.
Name : SINAGEO1
Group : Raster
With QGIS : 32602
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterRasterLayer
from qgis.core import QgsProcessingParameterRasterDestination
from qgis.core import QgsProcessingParameterFileDestination
from qgis.core import QgsCoordinateReferenceSystem
import processing


class Sinageo1(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        # Polígono de recorte
        self.addParameter(QgsProcessingParameterVectorLayer('limite_da_rea_de_estudo', 'Limite da área de estudo', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterLayer('mapa_de_referencia', 'Mapa de Referencia', defaultValue=None))
        # Comentário "usar modelos com resolução espacial de 30m." ou "Usar sistema de Coordenadas em metros" ... Etc.
        self.addParameter(QgsProcessingParameterRasterLayer('modelo_digital_de_elevao', 'Modelo Digital de Elevação', defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterDestination('Icr_classesFiltrado', 'ICR_Classes (filtrado)', createByDefault=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterFileDestination('Kappa', 'Kappa', fileFilter='Txt files (*.txt)', createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(9, model_feedback)
        results = {}
        outputs = {}

        # Recortar raster pela camada de máscara
        alg_params = {
            'ALPHA_BAND': False,
            'CROP_TO_CUTLINE': True,
            'DATA_TYPE': 0,  # Use Camada de entrada Tipo Dado
            'EXTRA': '',
            'INPUT': parameters['modelo_digital_de_elevao'],
            'KEEP_RESOLUTION': False,
            'MASK': parameters['limite_da_rea_de_estudo'],
            'MULTITHREADING': False,
            'NODATA': None,
            'OPTIONS': '',
            'SET_RESOLUTION': False,
            'SOURCE_CRS': None,
            'TARGET_CRS': None,
            'TARGET_EXTENT': None,
            'X_RESOLUTION': None,
            'Y_RESOLUTION': None,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RecortarRasterPelaCamadaDeMscara'] = processing.run('gdal:cliprasterbymasklayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Reprojetar coordenadas
        alg_params = {
            'DATA_TYPE': 0,  # Use Camada de entrada Tipo Dado
            'EXTRA': '',
            'INPUT': outputs['RecortarRasterPelaCamadaDeMscara']['OUTPUT'],
            'MULTITHREADING': False,
            'NODATA': None,
            'OPTIONS': '',
            'RESAMPLING': 0,  # Vizinho mais próximo
            'SOURCE_CRS': None,
            'TARGET_CRS': QgsCoordinateReferenceSystem('EPSG:31982'),
            'TARGET_EXTENT': None,
            'TARGET_EXTENT_CRS': None,
            'TARGET_RESOLUTION': None,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ReprojetarCoordenadas'] = processing.run('gdal:warpreproject', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # r.neighbors (SUAVIZA MODELO)
        alg_params = {
            '-a': False,
            '-c': False,
            'GRASS_RASTER_FORMAT_META': '',
            'GRASS_RASTER_FORMAT_OPT': '',
            'GRASS_REGION_CELLSIZE_PARAMETER': 0,
            'GRASS_REGION_PARAMETER': None,
            'gauss': None,
            'input': outputs['ReprojetarCoordenadas']['OUTPUT'],
            'method': 0,  # average
            'quantile': '',
            'selection': outputs['ReprojetarCoordenadas']['OUTPUT'],
            'size': 3,
            'weight': '',
            'output': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RneighborsSuavizaModelo'] = processing.run('grass7:r.neighbors', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Declividade
        alg_params = {
            'AS_PERCENT': True,
            'BAND': 1,
            'COMPUTE_EDGES': False,
            'EXTRA': '',
            'INPUT': outputs['RneighborsSuavizaModelo']['output'],
            'OPTIONS': '',
            'SCALE': 1,
            'ZEVENBERGEN': True,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Declividade'] = processing.run('gdal:slope', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # r.neighbors (ICR)
        alg_params = {
            '-a': False,
            '-c': True,
            'GRASS_RASTER_FORMAT_META': '',
            'GRASS_RASTER_FORMAT_OPT': '',
            'GRASS_REGION_CELLSIZE_PARAMETER': 0,
            'GRASS_REGION_PARAMETER': None,
            'gauss': None,
            'input': outputs['Declividade']['OUTPUT'],
            'method': 0,  # average
            'quantile': '',
            'selection': outputs['Declividade']['OUTPUT'],
            'size': 33,
            'weight': '',
            'output': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RneighborsIcr'] = processing.run('grass7:r.neighbors', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # Reclassificar por tabela
        alg_params = {
            'DATA_TYPE': 5,  # Float32
            'INPUT_RASTER': outputs['RneighborsIcr']['output'],
            'NODATA_FOR_MISSING': False,
            'NO_DATA': -9999,
            'RANGE_BOUNDARIES': 0,  # min < valor <= max
            'RASTER_BAND': 1,
            'TABLE': ['0','2.5','1','2.5','6','2','6','14','3','14','30','4','30','45','5','45','4000','6'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ReclassificarPorTabela'] = processing.run('native:reclassifybytable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # Crivo
        alg_params = {
            'EIGHT_CONNECTEDNESS': False,
            'EXTRA': '',
            'INPUT': outputs['ReclassificarPorTabela']['OUTPUT'],
            'MASK_LAYER': outputs['ReclassificarPorTabela']['OUTPUT'],
            'NO_MASK': False,
            'THRESHOLD': 3000,
            'OUTPUT': parameters['Icr_classesFiltrado']
        }
        outputs['Crivo'] = processing.run('gdal:sieve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Icr_classesFiltrado'] = outputs['Crivo']['OUTPUT']

        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}

        # r.kappa
        alg_params = {
            '-h': True,
            '-w': True,
            'GRASS_REGION_CELLSIZE_PARAMETER': 0,
            'GRASS_REGION_PARAMETER': None,
            'classification': outputs['Crivo']['OUTPUT'],
            'reference': parameters['mapa_de_referencia'],
            'title': 'ACCURACY ASSESSMENT',
            'output': parameters['Kappa']
        }
        outputs['Rkappa'] = processing.run('grass7:r.kappa', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Kappa'] = outputs['Rkappa']['output']

        feedback.setCurrentStep(8)
        if feedback.isCanceled():
            return {}

        # configurar estilo de camada
        alg_params = {
            'INPUT': outputs['Crivo']['OUTPUT'],
            'STYLE': 'C:\\Users\\TONY2\\OneDrive - ufpr.br\\ufpr\\SINAGEO2023\\estilo_icr.qml'
        }
        outputs['ConfigurarEstiloDeCamada'] = processing.run('native:setlayerstyle', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        return results

    def name(self):
        return 'SINAGEO1'

    def displayName(self):
        return 'SINAGEO1'

    def group(self):
        return 'Raster'

    def groupId(self):
        return 'Raster'

    def createInstance(self):
        return Sinageo1()

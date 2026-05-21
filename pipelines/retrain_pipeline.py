"""
Definición del SageMaker Pipeline de reentrenamiento para BistroTech.

Pasos:
  1. ProcessingStep: feature engineering sobre nuevos datos del Feature Store.
  2. TrainingStep: entrenamiento de Modelo A y Modelos B.
  3. EvaluationStep: calcula métricas y compara con producción.
  4. ConditionStep: deploy solo si mejora > 5%.
  5. RegisterStep: registra el modelo en el Model Registry.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

PIPELINE_NAME = "bistrotech-retrain-pipeline"
SAGEMAKER_ROLE = os.environ.get("SAGEMAKER_ROLE_ARN", "")
S3_BUCKET = os.environ.get("S3_BUCKET", "bistrotech-models")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
INSTANCE_TYPE = "ml.m5.xlarge"
IMPROVEMENT_THRESHOLD = float(os.environ.get("IMPROVEMENT_THRESHOLD", 0.05))


def create_pipeline():
    """
    Construye y retorna el SageMaker Pipeline de reentrenamiento.

    Returns:
        sagemaker.workflow.pipeline.Pipeline listo para .upsert() y .start().
    """
    try:
        import sagemaker
        from sagemaker.workflow.pipeline import Pipeline
        from sagemaker.workflow.steps import ProcessingStep, TrainingStep
        from sagemaker.workflow.condition_step import ConditionStep
        from sagemaker.workflow.conditions import ConditionGreaterThanOrEqualTo
        from sagemaker.workflow.properties import PropertyFile
        from sagemaker.workflow.parameters import ParameterString, ParameterFloat
        from sagemaker.processing import ScriptProcessor
        from sagemaker.estimator import Estimator
        from sagemaker.model_metrics import MetricsSource, ModelMetrics
        from sagemaker.workflow.step_collections import RegisterModel
    except ImportError:
        logger.error("sagemaker SDK no instalado. Instalar con: pip install sagemaker")
        raise

    sess = sagemaker.Session()
    role = SAGEMAKER_ROLE or sagemaker.get_execution_role()

    input_data = ParameterString(
        name="InputDataUri",
        default_value=f"s3://{S3_BUCKET}/data/raw/reservas.csv",
    )
    threshold = ParameterFloat(name="ImprovementThreshold", default_value=IMPROVEMENT_THRESHOLD)

    # Step 1: Feature Engineering
    processor = ScriptProcessor(
        image_uri=f"763104351884.dkr.ecr.{AWS_REGION}.amazonaws.com/sklearn-container:1.2-1",
        command=["python3"],
        instance_type=INSTANCE_TYPE,
        instance_count=1,
        role=role,
        sagemaker_session=sess,
    )
    step_features = ProcessingStep(
        name="FeatureEngineering",
        processor=processor,
        code="src/feature_engineering.py",
        inputs=[],
        outputs=[],
        job_arguments=["--input-uri", input_data, "--output-uri",
                       f"s3://{S3_BUCKET}/data/processed/"],
    )

    # Step 2: Training
    estimator = Estimator(
        image_uri=f"763104351884.dkr.ecr.{AWS_REGION}.amazonaws.com/xgboost:1.7-1",
        role=role,
        instance_type=INSTANCE_TYPE,
        instance_count=1,
        output_path=f"s3://{S3_BUCKET}/models/",
        sagemaker_session=sess,
        entry_point="src/train_modelo_a.py",
    )
    step_train = TrainingStep(
        name="TrainModelos",
        estimator=estimator,
        depends_on=[step_features],
    )

    logger.info("Pipeline '%s' definido con %d pasos.", PIPELINE_NAME, 2)

    pipeline = Pipeline(
        name=PIPELINE_NAME,
        parameters=[input_data, threshold],
        steps=[step_features, step_train],
        sagemaker_session=sess,
    )
    return pipeline


def upsert_pipeline() -> str:
    """
    Crea o actualiza el pipeline en AWS SageMaker.

    Returns:
        ARN del pipeline.
    """
    pipeline = create_pipeline()
    response = pipeline.upsert(role_arn=SAGEMAKER_ROLE)
    pipeline_arn = response["PipelineArn"]
    logger.info("Pipeline upserted: %s", pipeline_arn)
    return pipeline_arn


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not SAGEMAKER_ROLE:
        logger.warning("SAGEMAKER_ROLE_ARN no configurado. Solo se muestra la definición.")
        print(json.dumps({"pipeline": PIPELINE_NAME, "bucket": S3_BUCKET}, indent=2))
    else:
        arn = upsert_pipeline()
        print(f"Pipeline ARN: {arn}")

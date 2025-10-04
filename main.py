from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from kubernetes import client, config

# 쿠버네티스 설정 로드
config.load_incluster_config()
core_api = client.CoreV1Api()
apps_api = client.AppsV1Api()

app = FastAPI()

class User(BaseModel):
    username: str

# DB Deployment 생성 함수
def create_db_deployment(username: str):
    db_name = f"db-{username}"
    container = client.V1Container(
        name="postgres",
        image="postgres:13",
        ports=[client.V1ContainerPort(container_port=5432)],
        env=[client.V1EnvVar(name="POSTGRES_PASSWORD", value="supersecret")]
    )
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": db_name}),
        spec=client.V1PodSpec(containers=[container])
    )
    spec = client.V1DeploymentSpec(
        replicas=1,
        template=template,
        selector=client.V1LabelSelector(match_labels={"app": db_name})
    )
    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=db_name),
        spec=spec
    )
    return deployment

# DB Service 생성 함수
def create_db_service(username: str):
    db_name = f"db-{username}"
    spec = client.V1ServiceSpec(
        selector={"app": db_name},
        ports=[client.V1ServicePort(port=5432, target_port=5432)]
    )
    service = client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(name=db_name),
        spec=spec
    )
    return service

@app.post("/api/signup")
def signup(user: User):
    username = user.username.lower()
    db_name = f"db-{username}"
    
    try:
        # 1. DB Deployment 생성
        deployment_spec = create_db_deployment(username)
        apps_api.create_namespaced_deployment(body=deployment_spec, namespace="default")
        
        # 2. DB Service 생성
        service_spec = create_db_service(username)
        core_api.create_namespaced_service(body=service_spec, namespace="default")
        
        return {"message": f"Database resources for {username} are being created."}
    except client.ApiException as e:
        # 이미 존재하는 경우 등의 에러 처리
        if e.status == 409:
            raise HTTPException(status_code=409, detail="User already exists.")
        raise HTTPException(status_code=500, detail=f"Kubernetes API Error: {e.reason}")
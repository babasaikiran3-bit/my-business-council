# Kubernetes Deployment

This directory contains the default Kubernetes deployment manifest for LLM Council.

## Included Resources

The combined manifest in [llm-council.yaml](llm-council.yaml) creates:

- a namespace
- a persistent volume claim for conversation JSON files
- a backend deployment and service
- a frontend deployment and service
- an ingress for public HTTP access

## Before You Apply It

Update these values first:

- backend image name
- frontend image name
- ingress host
- storage class settings if your cluster requires them

## Required Secret

Create the OpenRouter secret before applying the manifest:

```bash
kubectl create namespace llm-council
kubectl create secret generic llm-council-secrets \
  --namespace llm-council \
  --from-literal=OPENROUTER_API_KEY=sk-or-v1-...
```

## Deploy

```bash
kubectl apply -f k8s/llm-council.yaml
```

## Update

```bash
kubectl apply -f k8s/llm-council.yaml
kubectl rollout status deployment/llm-council-backend -n llm-council
kubectl rollout status deployment/llm-council-frontend -n llm-council
```

## Remove

```bash
kubectl delete -f k8s/llm-council.yaml
```

## Operational Notes

- The frontend image serves static files through Nginx and proxies `/api/*` to the backend service.
- The ingress annotations in the manifest disable proxy buffering so the streaming endpoint can work correctly.
- Because persistence is local JSON on a mounted volume, the backend deployment should remain a single replica.

# Kubernetes deployment

Runs each submission as a **Job** created through the API, instead of as a
sibling container started through the Docker socket.

## Why

The Docker backend mounts `/var/run/docker.sock` so it can start sibling
containers. That socket is root-equivalent on the host: a container escape in
the API owns the node, and the mitigation is "run nothing else on that
instance". Under Kubernetes the API creates a Job per submission instead, so
no pod mounts a runtime socket at all.

## How the guarantees translate

| Docker backend | Kubernetes backend |
| --- | --- |
| `--network none` | NetworkPolicy denying all egress |
| `--memory` / `--cpus` | `resources.limits` |
| `--pids-limit` | *(no equivalent, see Gaps)* |
| `--user 10001` | `securityContext.runAsUser` |
| `--cap-drop ALL` | `capabilities.drop: [ALL]` |
| `--security-opt no-new-privileges` | `allowPrivilegeEscalation: false` |
| `--read-only` | `readOnlyRootFilesystem: true` |
| host-side timeout kill | `activeDeadlineSeconds` |
| *(none)* | `automountServiceAccountToken: false` |

That last row is the one Docker cannot express: the runner pod carries no
credentials for the API that is running it.

## The CNI matters more than the manifest

`--network none` is enforced by the container runtime. A NetworkPolicy is
enforced by the **CNI plugin**, and a CNI that does not implement NetworkPolicy
accepts the object and ignores it. No error, no warning, no enforcement.

kind's default CNI (kindnet) is one of those. Measured directly:

```
kindnet:  egress from runner pod -> REACHABLE
Calico:   egress from runner pod -> blocked
```

So `kind-cluster.yaml` sets `disableDefaultCNI: true` and Calico is installed
in its place. On a managed cluster check the provider's CNI actually enforces
policy. On EKS the default VPC CNI does not, without Calico installed
alongside it.

## Running it locally

```bash
kind create cluster --name algobattle --config deploy/k8s/kind-cluster.yaml
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.2/manifests/calico.yaml
kubectl wait --for=condition=ready pod -l k8s-app=calico-node -n kube-system --timeout=300s

docker build -f sandbox/python.Dockerfile -t algobattle-sandbox-python:latest sandbox/
kind load docker-image algobattle-sandbox-python:latest --name algobattle

kubectl apply -f deploy/k8s/00-namespace.yaml \
              -f deploy/k8s/01-rbac.yaml \
              -f deploy/k8s/02-networkpolicy.yaml

cd backend && SANDBOX_NAMESPACE=algobattle python -m pytest tests/test_sandbox_k8s.py -v
```

CI does exactly this on every change to the sandbox or these manifests.

## Gaps

- **Python only.** C++ and Java still run through the Docker backend. Their
  images are 1.9 GB and 705 MB, and compilation inside a read-only rootfs
  needs a larger writable `/tmp` than the 64 Mi the Python runner gets.
- **No pid ceiling.** `--pids-limit` has no pod-spec equivalent; capping
  processes needs a RuntimeClass or a kernel-level sandbox such as gVisor.
- **Cold start.** A Job takes roughly 3.4 s end to end against ~150 ms for
  `docker run` (scheduling, image pull check, and pod startup). Fine for a
  benchmark that already takes seconds; too slow for the "Test Run" button
  without a warm pool.
- **SQLite on an emptyDir.** Ratings live only as long as the pod. Durability
  needs a PVC or a real database.
- **One replica.** Rooms and brackets are in-process state, so a second
  replica would put players in rooms that cannot see each other.

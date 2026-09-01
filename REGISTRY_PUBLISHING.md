# Publishing KIE.ai Nodes Next to ComfyUI-Manager

The package already contains the official Comfy Registry GitHub Actions workflow.

Before the first publication:

1. Create/choose the final public GitHub repository.
2. Add its URL as `Repository = "https://github.com/..."` under `[project.urls]` in `pyproject.toml`.
3. Create a publisher at https://registry.comfy.org/ and replace `PublisherId` in `pyproject.toml` if `felipe-kie-next` is not the registered publisher ID.
4. Create a Registry publishing API key.
5. In the GitHub repository, add it as the Actions secret `REGISTRY_ACCESS_TOKEN`.
6. Run **Publish to Comfy registry** or bump `pyproject.toml` on `main`.

After publication, ComfyUI-Manager can install and update the node pack through the Registry without a manual folder/terminal workflow.


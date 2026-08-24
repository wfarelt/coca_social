from .models import Branch


def branch_navigation(request):
    branches = Branch.objects.filter(is_active=True).order_by("name")
    selected_branch_id = request.session.get("selected_branch_id")
    selected_branch = None
    if selected_branch_id:
        selected_branch = branches.filter(pk=selected_branch_id).first()
    if selected_branch is None:
        selected_branch = branches.first()
    return {
        "topbar_branches": branches,
        "selected_topbar_branch": selected_branch,
    }
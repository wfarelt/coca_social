from .models import Branch


def selected_branch_for_request(request):
    branches = Branch.objects.filter(is_active=True).order_by("name")
    selected_branch_id = request.session.get("selected_branch_id")
    if selected_branch_id:
        selected_branch = branches.filter(pk=selected_branch_id).first()
        if selected_branch is not None:
            return selected_branch
    return branches.first()


def branch_navigation(request):
    branches = Branch.objects.filter(is_active=True).order_by("name")
    return {
        "topbar_branches": branches,
        "selected_topbar_branch": selected_branch_for_request(request),
    }
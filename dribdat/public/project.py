# -*- coding: utf-8 -*-
"""Views related to project management."""
from flask import (
    Blueprint, request, render_template, flash, url_for, redirect
)
from flask_login import login_required, current_user

from dribdat.user.models import Event, Project, Activity, User
from dribdat.public.forms import (
    ProjectNew, ProjectForm, ProjectDetailForm,
    ProjectPost, ProjectBoost, ProjectComment,
)
from dribdat.database import db
from dribdat.extensions import cache
from dribdat.aggregation import (
    SyncProjectData, GetProjectData,
    ProjectActivity, IsProjectStarred,
)
from dribdat.user import (
    validateProjectData, projectProgressList, isUserActive,
)
from ..decorators import admin_required
from urllib.parse import quote_plus

blueprint = Blueprint('project', __name__,
                      static_folder="../static", url_prefix='/project')


def current_event(): return Event.current()


@blueprint.route('/<int:project_id>')
def project_view(project_id):
    return project_action(project_id, None)


@blueprint.route('/<int:project_id>/log')
def project_view_posted(project_id):
    return project_action(project_id, None)


@blueprint.route('/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def project_edit(project_id):
    return project_edit_action(project_id)


@blueprint.route('/<int:project_id>/details', methods=['GET', 'POST'])
@login_required
def project_details(project_id):
    return project_edit_action(project_id, True)


def project_edit_action(project_id, detail_view=False):
    """ Project editing handler """
    project = Project.query.filter_by(id=project_id).first_or_404()
    starred = IsProjectStarred(project, current_user)
    allow_edit = starred or (isUserActive(current_user)
                             and current_user.is_admin)
    if not allow_edit:
        flash('You do not have access to edit this project.', 'warning')
        return project_action(project_id, None)
    if not detail_view:
        form = ProjectForm(obj=project, next=request.args.get('next'))
        form.category_id.choices = [(c.id, c.name)
                                    for c in project.categories_all()]
        if len(form.category_id.choices) > 0:
            form.category_id.choices.insert(0, (-1, ''))
        else:
            del form.category_id
    else:
        form = ProjectDetailForm(obj=project, next=request.args.get('next'))
    if form.validate_on_submit():
        del form.id
        form.populate_obj(project)
        project.update()
        db.session.add(project)
        db.session.commit()
        cache.clear()
        flash('Project updated.', 'success')
        project_action(project_id, 'update', False)
        return redirect(url_for('project.project_view', project_id=project.id))
    return render_template(
        'public/projectedit.html', detail_view=detail_view,
        current_event=project.event, project=project, form=form,
        active="projects"
    )


@blueprint.route('/<int:project_id>/boost', methods=['GET', 'POST'])
@login_required
def project_boost(project_id):
    project = Project.query.filter_by(id=project_id).first_or_404()
    event = project.event

    allow_post = not current_user.is_anonymous and current_user.is_admin
    if not allow_post:
        flash('You do not have access to boost this project.', 'warning')
        return project_action(project_id, None)

    form = ProjectBoost(obj=project, next=request.args.get('next'))
    # TODO: load from a YAML file or from the Presets config
    form.boost_type.choices = [
        '---',
        'Awesome sauce',
        'Data wizards',
        'Glorious purpose',
        'Top tutorial',
        'Super committers',
    ]

    # Process form
    if form.validate_on_submit():
        # Update project data
        cache.clear()
        project_action(project_id, 'boost',
                       action=form.boost_type.data, text=form.note.data)
        flash('Thanks for your boost!', 'success')
        return project_view(project.id)

    return render_template(
        'public/projectboost.html',
        current_event=event, project=project, form=form,
        active="dribs"
    )


@blueprint.route('/<int:project_id>/post', methods=['GET', 'POST'])
@login_required
def project_post(project_id):
    project = Project.query.filter_by(id=project_id).first_or_404()
    event = project.event
    starred = IsProjectStarred(project, current_user)
    allow_post = starred
    # or (not current_user.is_anonymous and current_user.is_admin)
    # allow_post = allow_post and not event.lock_resources
    if not allow_post:
        flash('You do not have access to post to this project.', 'warning')
        return project_action(project_id, None)
    form = ProjectPost(obj=project, next=request.args.get('next'))
    # Evaluate project progress
    stage, all_valid = validateProjectData(project)
    # Process form
    if form.validate_on_submit():
        if form.has_progress.data:
            # Check and update progress
            found_next = False
            if all_valid:
                for a in projectProgressList(True, False):
                    if found_next:
                        project.progress = a[0]
                        flash("Promoted to stage '%s'" %
                              project.progress, 'info')
                        break
                    if a[0] == project.progress or \
                        not project.progress or \
                            project.progress < 0:
                        found_next = True
            # if not all_valid or not found_next:
            #    flash('Your project did not meet stage requirements.', 'info')

        # Update project data
        del form.id
        del form.has_progress
        form.populate_obj(project)
        project.update()
        db.session.add(project)
        db.session.commit()
        cache.clear()
        project_action(project_id, 'update',
                       action='post', text=form.note.data)

        flash("Thanks for sharing!", 'success')

        # Continue with project autoupdate
        if project.is_autoupdateable:
            return project_autoupdate(project.id)
        else:
            return redirect(url_for(
                'project.project_view_posted', project_id=project.id))

    return render_template(
        'public/projectpost.html',
        current_event=event, project=project, form=form,
        stage=stage, all_valid=all_valid,
        active="dribs"
    )


@blueprint.route('/<int:project_id>/comment', methods=['GET', 'POST'])
@login_required
def project_comment(project_id):
    project = Project.query.filter_by(id=project_id).first_or_404()
    event = project.event
    form = ProjectComment(obj=project, next=request.args.get('next'))
    # Process form
    if form.validate_on_submit():
        # Update project data
        project_action(project_id, 'review',
                       action='post', text=form.note.data)

        flash("Thanks for your feedback!", 'success')
        return redirect(url_for(
            'project.project_view_posted', project_id=project.id))

    return render_template(
        'public/projectpost.html',
        current_event=event, project=project, form=form,
        active="dribs"
    )


@blueprint.route('/<int:project_id>/unpost/<int:activity_id>', methods=['GET'])
@login_required
def post_delete(project_id, activity_id):
    project = Project.query.filter_by(id=project_id).first_or_404()
    activity = Activity.query.filter_by(id=activity_id).first_or_404()
    activity.delete()
    flash('The post has been deleted.', 'success')
    return project_view(project.id)


@blueprint.route('/<int:project_id>/undo/<int:activity_id>', methods=['GET'])
@login_required
def post_revert(project_id, activity_id):
    project = Project.query.filter_by(id=project_id).first_or_404()
    activity = Activity.query.filter_by(id=activity_id).first_or_404()
    if not activity.project_version:
        flash('Could not revert: data not available.', 'warning')
    elif activity.project_version == 0:
        flash('Could not revert: this is the earliest version.', 'warning')
    else:
        revert_to = activity.project_version
        project.versions[revert_to - 1].revert()
        flash('Project data reverted to version %d.' % revert_to, 'success')
        return project_view(project.id)
    return redirect(url_for(
        'project.project_view_posted', project_id=project.id))


def getSuggestionsForStage(progress):
    """ Get all projects which are published in a resource-type event """
    project_list = []
    resource_events = [e.id for e in Event.query.filter_by(
        lock_resources=True).all()]
    for eid in resource_events:
        projects = Project.query.filter_by(
            event_id=eid, is_hidden=False, progress=progress)
        project_list.extend([p.data for p in projects.all()])
    return project_list


def project_action(project_id, of_type=None, as_view=True, then_redirect=False,
                   action=None, text=None, for_user=current_user):
    project = Project.query.filter_by(id=project_id).first_or_404()
    event = project.event
    if of_type is not None:
        ProjectActivity(project, of_type, for_user, action, text)
    if not as_view:
        return True
    if then_redirect:
        return redirect(url_for('project.project_view', project_id=project.id))
    # The next line seems rather inefficient
    starred = IsProjectStarred(project, for_user)
    # Figure out permissions (hackybehack!)
    allow_edit = not current_user.is_anonymous and current_user.is_admin
    lock_editing = event.lock_editing
    allow_post = starred and not event.lock_resources
    allow_edit = (starred or allow_edit) and not lock_editing
    # Obtain list of team members (performance!)
    project_team = project.get_team()
    if allow_post:
        # Evaluate project progress
        stage, all_valid = validateProjectData(project)
        # Collect resource tips
        suggestions = []
        if not event.lock_resources:
            suggestions = getSuggestionsForStage(project.progress)
        # Suggest missing team roles
        missing_roles = project.get_missing_roles()
    else:
        suggestions, stage, all_valid, missing_roles = None, None, None, None
    # latest_activity = project.latest_activity() # obsolete
    project_dribs = project.all_dribs()
    project_badge = [s for s in project_dribs if s['name'] == 'boost']
    # Select available project image
    if project.image_url:
        project_image_url = project.image_url
    elif event.logo_url:
        project_image_url = event.logo_url
    else:
        project_image_url = url_for(
            'static', filename='img/badge-black.png', _external=True)
    # Generate social links
    share = {
        'text': quote_plus(" ".join([
            project.hashtag or project.name,
            event.hashtags or '#dribdat' ])),
        'url': quote_plus(request.url)
    }
    # Generate a certificate if available
    cert_path = None
    if current_user and not current_user.is_anonymous:
        cert_path = current_user.get_cert_path(event)
    # Dump all that data into a template
    return render_template(
        'public/project.html', current_event=event, project=project,
        project_starred=starred, project_team=project_team,
        project_badge=project_badge, project_dribs=project_dribs,
        project_image_url=project_image_url,
        allow_edit=allow_edit, allow_post=allow_post,
        lock_editing=lock_editing, missing_roles=missing_roles,
        stage=stage, all_valid=all_valid, cert_path=cert_path,
        suggestions=suggestions, share=share,
        active="projects"
    )


@blueprint.route('/<int:project_id>/star/me', methods=['GET', 'POST'])
@login_required
def project_star(project_id):
    if not isUserActive(current_user):
        flash(
            "User currently not allowed to join projects - please contact "
            + " organizers for activation.", 'warning'
        )
        return redirect(url_for('project.project_view', project_id=project_id))
    flash('Welcome to the team!', 'success')
    return project_action(project_id, 'star', then_redirect=True)


@blueprint.route('/<int:project_id>/star', methods=['POST'])
@login_required
@admin_required
def project_star_user(project_id):
    username = request.form['username']
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash("User [%s] not found. Please try again." % username, 'warning')
        return redirect(url_for('project.project_view', project_id=project_id))
    flash('Added %s to the team!' % username, 'success')
    return project_action(
        project_id, 'star', then_redirect=True, for_user=user)


@blueprint.route('/<int:project_id>/unstar/me', methods=['GET', 'POST'])
@login_required
def project_unstar_me(project_id):
    flash('You have left the project', 'success')
    return project_action(project_id, 'unstar', then_redirect=True)


@blueprint.route('/<int:project_id>/unstar/<int:user_id>', methods=['GET'])
@login_required
@admin_required
def project_unstar(project_id, user_id):
    user = User.query.filter_by(id=user_id).first_or_404()
    project = Project.query.filter_by(id=project_id).first_or_404()
    flash('User %s has left the project' % user.username, 'success')
    return project_action(
        project.id, 'unstar', then_redirect=True, for_user=user
    )


@blueprint.route('/event/<int:event_id>/project/new', methods=['GET', 'POST'])
@login_required
def project_new(event_id):
    if not isUserActive(current_user):
        flash(
            "Your account needs to be activated - "
            + " please contact an organizer.", 'warning'
        )
        return redirect(url_for('public.event', event_id=event_id))
    form = None
    event = Event.query.filter_by(id=event_id).first_or_404()
    if event.lock_starting:
        flash('Starting a new project is disabled for this event.', 'error')
        return redirect(url_for('public.event', event_id=event.id))
    if not isUserActive(current_user):
        flash('Your user account is not permitted to start projects.', 'error')
        return redirect(url_for('public.event', event_id=event.id))
    # Collect resource tips
    suggestions = []
    if not event.lock_resources:
        suggestions = getSuggestionsForStage(0)
    # Project form
    project = Project()
    project.user_id = current_user.id
    form = ProjectNew(obj=project, next=request.args.get('next'))
    form.category_id.choices = [(c.id, c.name)
                                for c in project.categories_all(event)]
    if len(form.category_id.choices) > 0:
        form.category_id.choices.insert(0, (-1, ''))
    else:
        del form.category_id
    if form.validate_on_submit():
        tpl_id = None
        if form.template.data:
            tpl_id = form.template.data
        del form.id
        del form.template
        form.populate_obj(project)
        if tpl_id:
            template = Project.query.get(tpl_id)
            project.longtext = template.longtext
            project.image_url = template.image_url
            project.source_url = template.source_url
            project.webpage_url = template.webpage_url
            project.download_url = template.download_url
        # Check event state
        project.event = event
        if event.has_started:
            project.progress = 5  # Start as team
        else:
            project.progress = -1  # Start as challenge
        # Update the project
        project.update()
        db.session.add(project)
        db.session.commit()
        flash('Now invite your team to Join this page!', 'success')
        project_action(project.id, 'create', False)
        cache.clear()
        if event.has_started:
            project_action(project.id, 'star', False)  # Join team
        if len(project.autotext_url) > 1:
            return project_autoupdate(project.id)
        else:
            purl = url_for('project.project_view', project_id=project.id)
            return redirect(purl)
    return render_template(
        'public/projectnew.html',
        current_event=event, form=form, suggestions=suggestions,
        active="projects"
    )


@blueprint.route('/<int:project_id>/autoupdate')
@login_required
def project_autoupdate(project_id):
    project = Project.query.filter_by(id=project_id).first_or_404()
    if not project.is_autoupdateable:
        return project_action(project_id)
    # Check user permissions
    starred = IsProjectStarred(project, current_user)
    allow_edit = starred or (
        not current_user.is_anonymous and current_user.is_admin)
    if not allow_edit or project.is_hidden:
        flash('You may not sync this project.', 'warning')
        return redirect(url_for('project.project_view', project_id=project_id))
    # Start update process
    has_autotext = project.autotext and len(project.autotext) > 1
    data = GetProjectData(project.autotext_url)
    if not data or 'name' not in data:
        flash("To Sync: ensure a README on the remote site.", 'warning')
        return redirect(url_for('project.project_view', project_id=project_id))
    SyncProjectData(project, data)
    # Confirmation messages
    if not has_autotext:
        if project.autotext and len(project.autotext) > 1:
            project_action(project.id, 'update', action='sync',
                           text=str(len(project.autotext)) + ' bytes')
            flash("Thanks for contributing on %s" % data['type'], 'success')
        else:
            flash("Could not sync: remote README has no data.", 'warning')
    return redirect(url_for(
        'project.project_view_posted', project_id=project_id))

"""CLI commands for managing Borg mounts."""

import click
from flask.cli import with_appcontext
from flask import current_app
import json
from datetime import datetime

from citadel.backup.mount_management import (
    get_all_active_mounts,
    get_orphaned_mounts,
    unmount_orphaned,
    find_borg_mounts,
    force_unmount_all
)

@click.group()
def mounts_cli():
    """Commands for managing Borg mounts."""
    pass

@mounts_cli.command('list')
@with_appcontext
def list_mounts():
    """List all active mounts tracked by the application."""
    active_mounts = get_all_active_mounts()
    
    if not active_mounts:
        click.echo("No active mounts found.")
        return
    
    click.echo(f"Found {len(active_mounts)} active mounts:")
    for mount in active_mounts:
        click.echo(f"Job {mount['job_id']}: {mount['archive_name']} mounted at {mount['mount_point']} ({mount['mounted_at']})")

@mounts_cli.command('list-orphaned')
@click.option('--hours', default=24, help='Age in hours to consider a mount orphaned')
@with_appcontext
def list_orphaned_mounts(hours):
    """List orphaned mounts (mounts older than specified hours)."""
    orphaned_mounts = get_orphaned_mounts(max_age_hours=hours)
    
    if not orphaned_mounts:
        click.echo(f"No orphaned mounts found (older than {hours} hours).")
        return
    
    click.echo(f"Found {len(orphaned_mounts)} orphaned mounts:")
    for mount in orphaned_mounts:
        click.echo(f"Job {mount['job_id']}: {mount['archive_name']} mounted at {mount['mount_point']} ({mount['mounted_at']})")

@mounts_cli.command('cleanup')
@click.option('--hours', default=24, help='Age in hours to consider a mount orphaned')
@click.option('--force', is_flag=True, help='Force immediate unmounting instead of queuing')
@click.confirmation_option(prompt='Are you sure you want to unmount orphaned archives?')
@with_appcontext
def cleanup_orphaned_mounts(hours, force):
    """Unmount orphaned mounts (mounts older than specified hours)."""
    results = unmount_orphaned(max_age_hours=hours, force=force)
    
    if not results:
        click.echo(f"No orphaned mounts found (older than {hours} hours).")
        return
    
    click.echo(f"Processed {len(results)} orphaned mounts:")
    for result in results:
        status = result['status']
        job_id = result['job_id']
        mount_point = result['mount_point']
        
        if status == 'error':
            click.echo(f"Error unmounting Job {job_id} at {mount_point}: {result.get('error', 'Unknown error')}")
        else:
            action = "Unmounted" if status == 'unmounted' else "Queued unmount for"
            click.echo(f"{action} Job {job_id} at {mount_point}")

@mounts_cli.command('system-list')
@with_appcontext
def list_system_mounts():
    """List all FUSE mounts in the system that appear to be Borg mounts."""
    system_mounts = find_borg_mounts()
    
    if not system_mounts:
        click.echo("No Borg mounts found in the system.")
        return
    
    click.echo(f"Found {len(system_mounts)} Borg mounts in the system:")
    for mount in system_mounts:
        click.echo(f"{mount['device']} mounted at {mount['mount_point']} (type: {mount['type']})")

@mounts_cli.command('force-unmount-all')
@click.confirmation_option(prompt='Are you sure you want to force unmount ALL Borg mounts? This is potentially destructive!')
@with_appcontext
def force_unmount_all_cmd():
    """Force unmount all Borg mounts in the system."""
    results = force_unmount_all()
    
    if not results:
        click.echo("No mounts were found to unmount.")
        return
    
    click.echo(f"Processed {len(results)} mounts:")
    for result in results:
        status = result['status']
        mount_point = result['mount_point']
        
        if status == 'error' or status == 'failed':
            click.echo(f"Error unmounting {mount_point}: {result.get('error', 'Unknown error')}")
        else:
            click.echo(f"Unmounted {mount_point}")

# Add a debug command to dump the mount info
@mounts_cli.command('debug-info')
@with_appcontext
def debug_mount_info():
    """Dump debug information about mounts."""
    active_mounts = get_all_active_mounts()
    orphaned_mounts = get_orphaned_mounts()
    system_mounts = find_borg_mounts()
    
    debug_info = {
        'active_mounts': active_mounts,
        'orphaned_mounts': orphaned_mounts,
        'system_mounts': system_mounts,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    click.echo(json.dumps(debug_info, indent=2))

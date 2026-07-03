"""
Hub update history table operations for Mycelium.

Audit log for in-field updates of the Mycelium app itself (see
api/services/hub_update_service.py and Settings -> Hub Updates). Distinct from
ota_history, which tracks Spore/Hyphae firmware.
"""

from storage.db_utils import execute_query, execute_insert, execute_update, get_timestamp


def record_update_start(from_version, from_ref, to_ref, initiated_by=None):
    """Insert a 'pending' row when an update is initiated. Returns its update_id."""
    query = """
    INSERT INTO hub_update_history
        (from_version, from_ref, to_ref, status, initiated_by, started_at)
    VALUES (?, ?, ?, 'pending', ?, ?)
    """
    return execute_insert(
        query, (from_version, from_ref, to_ref, initiated_by, get_timestamp())
    )


def record_update_result(update_id, status, to_version=None, to_sha=None, error_message=None):
    """Finalize an update row with its outcome (success/failed/rolled_back)."""
    query = """
    UPDATE hub_update_history
    SET status = ?, to_version = ?, to_sha = ?, error_message = ?, completed_at = ?
    WHERE update_id = ?
    """
    return execute_update(
        query, (status, to_version, to_sha, error_message, get_timestamp(), update_id)
    )


def list_updates(limit=20):
    """Most recent update events, newest first."""
    return execute_query(
        "SELECT * FROM hub_update_history ORDER BY started_at DESC LIMIT ?", (limit,)
    )


def reconcile_interrupted():
    """Mark any lingering 'pending' rows as failed.

    A genuine in-flight update restarts the service (dropping the session), so any
    'pending' row still visible when the Updates page renders is from a run that
    was interrupted (power loss, crash) and never recorded a result. Returns the
    number of rows reconciled.
    """
    query = """
    UPDATE hub_update_history
    SET status = 'failed',
        error_message = COALESCE(error_message, 'interrupted before completion'),
        completed_at = ?
    WHERE status = 'pending'
    """
    return execute_update(query, (get_timestamp(),))

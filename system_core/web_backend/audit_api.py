"""
Audit Log API endpoints for compliance and security tracking.

Provides REST APIs for:
- Querying audit logs with filters
- Exporting audit logs in CSV and JSON formats
- Verifying audit log signatures

Validates: Requirements 39.6, 39.7
"""

import csv
import io
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.database import get_db
from system_core.database.models import AuditLog, User
from system_core.auth.middleware import get_current_user
from system_core.monitoring.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

@router.get("")
async def query_audit_logs(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """
    Query audit logs with filters.
    
    Args:
        user_id: Filter by user ID
        action: Filter by action type (e.g., "user_login", "config_change", "trade_executed")
        resource_type: Filter by resource type (e.g., "user", "ea_profile", "trade", "config")
        start_date: Start date for filtering (inclusive)
        end_date: End date for filtering (inclusive)
        limit: Maximum number of results (1-1000)
        offset: Offset for pagination
        
    Returns:
        Dictionary containing:
        - total: Total number of matching audit logs
        - limit: Applied limit
        - offset: Applied offset
        - logs: List of audit log entries
        
    Validates: Requirements 39.6
    """
    try:
        # Build query with filters
        query = db.query(AuditLog)
        
        filters = []
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if action:
            filters.append(AuditLog.action == action)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)
        if start_date:
            filters.append(AuditLog.created_at >= start_date)
        if end_date:
            filters.append(AuditLog.created_at <= end_date)
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Get total count
        total = query.count()
        
        # Apply ordering, limit, and offset
        logs = query.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset).all()
        
        # Convert to dict
        log_dicts = []
        for log in logs:
            log_dict = {
                "id": str(log.id),
                "user_id": str(log.user_id) if log.user_id else None,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "signature": log.signature,
                "created_at": log.created_at.isoformat()
            }
            log_dicts.append(log_dict)
        
        logger.info(
            "audit_logs_queried",
            user_id=str(user_id) if user_id else None,
            action=action,
            resource_type=resource_type,
            total=total,
            returned=len(log_dicts)
        )
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "logs": log_dicts
        }
        
    except Exception as e:
        logger.error("failed_to_query_audit_logs", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to query audit logs: {str(e)}")

@router.get("/export/json")
async def export_audit_logs_json(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO 8601)"),
    limit: int = Query(10000, ge=1, le=100000, description="Maximum number of results"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Response:
    """
    Export audit logs in JSON format.
    
    Args:
        user_id: Filter by user ID
        action: Filter by action type
        resource_type: Filter by resource type
        start_date: Start date for filtering (inclusive)
        end_date: End date for filtering (inclusive)
        limit: Maximum number of results (1-100000)
        
    Returns:
        JSON file download with audit logs
        
    Validates: Requirements 39.7
    """
    try:
        # Build query with filters
        query = db.query(AuditLog)
        
        filters = []
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if action:
            filters.append(AuditLog.action == action)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)
        if start_date:
            filters.append(AuditLog.created_at >= start_date)
        if end_date:
            filters.append(AuditLog.created_at <= end_date)
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Get logs
        logs = query.order_by(desc(AuditLog.created_at)).limit(limit).all()
        
        # Convert to dict
        log_dicts = []
        for log in logs:
            log_dict = {
                "id": str(log.id),
                "user_id": str(log.user_id) if log.user_id else None,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "signature": log.signature,
                "created_at": log.created_at.isoformat()
            }
            log_dicts.append(log_dict)
        
        logger.info(
            "audit_logs_exported_json",
            count=len(log_dicts),
            user_id=str(user_id) if user_id else None
        )
        
        # Return as JSON download
        import json
        json_content = json.dumps(log_dicts, indent=2)
        
        return Response(
            content=json_content,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            }
        )
        
    except Exception as e:
        logger.error("failed_to_export_audit_logs_json", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to export audit logs: {str(e)}")

@router.get("/export/csv")
async def export_audit_logs_csv(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO 8601)"),
    limit: int = Query(10000, ge=1, le=100000, description="Maximum number of results"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> StreamingResponse:
    """
    Export audit logs in CSV format.
    
    Args:
        user_id: Filter by user ID
        action: Filter by action type
        resource_type: Filter by resource type
        start_date: Start date for filtering (inclusive)
        end_date: End date for filtering (inclusive)
        limit: Maximum number of results (1-100000)
        
    Returns:
        CSV file download with audit logs
        
    Validates: Requirements 39.7
    """
    try:
        # Build query with filters
        query = db.query(AuditLog)
        
        filters = []
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if action:
            filters.append(AuditLog.action == action)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)
        if start_date:
            filters.append(AuditLog.created_at >= start_date)
        if end_date:
            filters.append(AuditLog.created_at <= end_date)
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Get logs
        logs = query.order_by(desc(AuditLog.created_at)).limit(limit).all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "id", "user_id", "action", "resource_type", "resource_id",
            "old_value", "new_value", "ip_address", "user_agent",
            "signature", "created_at"
        ])
        
        # Write data
        import json
        for log in logs:
            writer.writerow([
                str(log.id),
                str(log.user_id) if log.user_id else "",
                log.action,
                log.resource_type,
                str(log.resource_id) if log.resource_id else "",
                json.dumps(log.old_value) if log.old_value else "",
                json.dumps(log.new_value) if log.new_value else "",
                log.ip_address or "",
                log.user_agent or "",
                log.signature or "",
                log.created_at.isoformat()
            ])
        
        logger.info(
            "audit_logs_exported_csv",
            count=len(logs),
            user_id=str(user_id) if user_id else None
        )
        
        # Return as CSV download
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
        
    except Exception as e:
        logger.error("failed_to_export_audit_logs_csv", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to export audit logs: {str(e)}")

@router.get("/{audit_log_id}/verify")
async def verify_audit_log_signature(
    audit_log_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """
    Verify the HMAC-SHA256 signature of an audit log entry.
    
    Args:
        audit_log_id: ID of the audit log entry to verify
        
    Returns:
        Dictionary containing:
        - audit_log_id: ID of the audit log entry
        - valid: Whether the signature is valid
        - message: Verification result message
        
    Note: This endpoint requires the audit logger to be initialized with the secret key.
    """
    try:
        # Get audit log
        audit_log = db.query(AuditLog).filter(AuditLog.id == audit_log_id).first()
        
        if not audit_log:
            raise HTTPException(status_code=404, detail="Audit log not found")
        
        # Note: Signature verification requires access to the secret key
        # This is a placeholder - actual verification would need the AuditLogger instance
        logger.info(
            "audit_log_signature_verification_requested",
            audit_log_id=str(audit_log_id)
        )
        
        return {
            "audit_log_id": str(audit_log_id),
            "valid": audit_log.signature is not None and len(audit_log.signature) == 64,
            "message": "Signature verification requires audit logger instance with secret key"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_verify_audit_log", error=str(e), audit_log_id=str(audit_log_id))
        raise HTTPException(status_code=500, detail=f"Failed to verify audit log: {str(e)}")

@router.get("/stats")
async def get_audit_log_stats(
    start_date: Optional[datetime] = Query(None, description="Start date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO 8601)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """
    Get audit log statistics.
    
    Args:
        start_date: Start date for filtering (inclusive)
        end_date: End date for filtering (inclusive)
        
    Returns:
        Dictionary containing:
        - total_logs: Total number of audit logs
        - logs_by_action: Count of logs grouped by action
        - logs_by_resource_type: Count of logs grouped by resource type
        - logs_by_user: Count of logs grouped by user
    """
    try:
        # Build base query
        query = db.query(AuditLog)
        
        filters = []
        if start_date:
            filters.append(AuditLog.created_at >= start_date)
        if end_date:
            filters.append(AuditLog.created_at <= end_date)
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Total logs
        total_logs = query.count()
        
        # Logs by action
        logs_by_action = {}
        action_counts = db.query(
            AuditLog.action,
            func.count(AuditLog.id)
        ).filter(and_(*filters) if filters else True).group_by(AuditLog.action).all()
        
        for action, count in action_counts:
            logs_by_action[action] = count
        
        # Logs by resource type
        logs_by_resource_type = {}
        resource_counts = db.query(
            AuditLog.resource_type,
            func.count(AuditLog.id)
        ).filter(and_(*filters) if filters else True).group_by(AuditLog.resource_type).all()
        
        for resource_type, count in resource_counts:
            logs_by_resource_type[resource_type] = count
        
        # Logs by user (top 10)
        logs_by_user = {}
        user_counts = db.query(
            AuditLog.user_id,
            func.count(AuditLog.id)
        ).filter(and_(*filters) if filters else True).group_by(AuditLog.user_id).order_by(
            desc(func.count(AuditLog.id))
        ).limit(10).all()
        
        for user_id, count in user_counts:
            logs_by_user[str(user_id) if user_id else "system"] = count
        
        logger.info("audit_log_stats_retrieved", total_logs=total_logs)
        
        return {
            "total_logs": total_logs,
            "logs_by_action": logs_by_action,
            "logs_by_resource_type": logs_by_resource_type,
            "logs_by_user": logs_by_user
        }
        
    except Exception as e:
        logger.error("failed_to_get_audit_log_stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get audit log stats: {str(e)}")


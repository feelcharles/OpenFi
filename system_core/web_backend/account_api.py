"""
账户管理API
Account Management API

提供账户配置、风险参数设置等功能
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from system_core.config import get_logger, ConfigurationManager
from system_core.auth import get_current_user, require_permission

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


# ============================================
# Pydantic Models
# ============================================

class RiskManagementSettings(BaseModel):
    """风险管理设置"""
    max_daily_loss_percent: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="每日最大亏损百分比"
    )
    max_total_risk_percent: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="总风险百分比"
    )
    max_open_positions: int = Field(
        ...,
        ge=1,
        description="最大持仓数"
    )
    max_drawdown_percent: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="最大回撤百分比，达到此值强制平仓"
    )
    force_close_on_max_drawdown: bool = Field(
        default=True,
        description="达到最大回撤时是否强制平仓"
    )


class AccountSettings(BaseModel):
    """账户设置"""
    currency: str = Field(..., description="货币")
    leverage: Optional[int] = Field(None, description="杠杆")
    timezone: str = Field(..., description="时区")
    market: Optional[str] = Field(None, description="市场")


class AccountInfo(BaseModel):
    """账户信息"""
    account_id: str
    account_name: str
    platform: str
    account_type: str
    enabled: bool
    settings: AccountSettings
    risk_management: RiskManagementSettings


class UpdateRiskManagementRequest(BaseModel):
    """更新风险管理请求"""
    max_daily_loss_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    max_total_risk_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    max_open_positions: Optional[int] = Field(None, ge=1)
    max_drawdown_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    force_close_on_max_drawdown: Optional[bool] = None


class AccountStatusResponse(BaseModel):
    """账户状态响应"""
    account_id: str
    enabled: bool
    current_balance: float
    current_equity: float
    current_drawdown_percent: float
    open_positions: int
    daily_pnl: float
    daily_pnl_percent: float
    risk_status: str  # "safe", "warning", "critical"
    last_updated: datetime


# ============================================
# API Endpoints
# ============================================

@router.get("/", response_model=List[AccountInfo])
async def list_accounts(
    current_user: dict = Depends(get_current_user)
):
    """
    获取所有账户列表
    Get all accounts list
    """
    try:
        config_manager = ConfigurationManager()
        await config_manager.initialize()
        
        accounts_config = config_manager.get_config("accounts.yaml")
        
        if not accounts_config or "accounts" not in accounts_config:
            return []
        
        accounts = []
        for account in accounts_config["accounts"]:
            accounts.append(AccountInfo(
                account_id=account["account_id"],
                account_name=account["account_name"],
                platform=account["platform"],
                account_type=account["account_type"],
                enabled=account["enabled"],
                settings=AccountSettings(**account["settings"]),
                risk_management=RiskManagementSettings(**account["risk_management"])
            ))
        
        await config_manager.close()
        
        logger.info("accounts_listed", user=current_user.get("username"), count=len(accounts))
        return accounts
        
    except Exception as e:
        logger.error("list_accounts_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取账户列表失败: {str(e)}"
        )


@router.get("/{account_id}", response_model=AccountInfo)
async def get_account(
    account_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取指定账户信息
    Get specific account information
    """
    try:
        config_manager = ConfigurationManager()
        await config_manager.initialize()
        
        accounts_config = config_manager.get_config("accounts.yaml")
        
        if not accounts_config or "accounts" not in accounts_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="账户配置不存在"
            )
        
        account = None
        for acc in accounts_config["accounts"]:
            if acc["account_id"] == account_id:
                account = acc
                break
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"账户 {account_id} 不存在"
            )
        
        await config_manager.close()
        
        return AccountInfo(
            account_id=account["account_id"],
            account_name=account["account_name"],
            platform=account["platform"],
            account_type=account["account_type"],
            enabled=account["enabled"],
            settings=AccountSettings(**account["settings"]),
            risk_management=RiskManagementSettings(**account["risk_management"])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_account_error", account_id=account_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取账户信息失败: {str(e)}"
        )


@router.put("/{account_id}/risk-management", response_model=RiskManagementSettings)
async def update_risk_management(
    account_id: str,
    request: UpdateRiskManagementRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    更新账户风险管理设置
    Update account risk management settings
    
    需要管理员权限
    Requires admin permission
    """
    # 检查权限
    if not require_permission(current_user, "accounts", "write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改账户设置"
        )
    
    try:
        config_manager = ConfigurationManager()
        await config_manager.initialize()
        
        accounts_config = config_manager.get_config("accounts.yaml")
        
        if not accounts_config or "accounts" not in accounts_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="账户配置不存在"
            )
        
        # 查找并更新账户
        account_found = False
        for account in accounts_config["accounts"]:
            if account["account_id"] == account_id:
                account_found = True
                
                # 更新风险管理设置
                risk_mgmt = account["risk_management"]
                
                if request.max_daily_loss_percent is not None:
                    risk_mgmt["max_daily_loss_percent"] = request.max_daily_loss_percent
                
                if request.max_total_risk_percent is not None:
                    risk_mgmt["max_total_risk_percent"] = request.max_total_risk_percent
                
                if request.max_open_positions is not None:
                    risk_mgmt["max_open_positions"] = request.max_open_positions
                
                if request.max_drawdown_percent is not None:
                    risk_mgmt["max_drawdown_percent"] = request.max_drawdown_percent
                
                if request.force_close_on_max_drawdown is not None:
                    risk_mgmt["force_close_on_max_drawdown"] = request.force_close_on_max_drawdown
                
                break
        
        if not account_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"账户 {account_id} 不存在"
            )
        
        # 保存配置
        await config_manager.save_config("accounts.yaml", accounts_config)
        await config_manager.close()
        
        logger.info(
            "risk_management_updated",
            account_id=account_id,
            user=current_user.get("username"),
            changes=request.dict(exclude_none=True)
        )
        
        # 返回更新后的设置
        return RiskManagementSettings(**account["risk_management"])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_risk_management_error", account_id=account_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新风险管理设置失败: {str(e)}"
        )


@router.post("/{account_id}/enable")
async def enable_account(
    account_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    启用账户
    Enable account
    
    需要管理员权限
    Requires admin permission
    """
    if not require_permission(current_user, "accounts", "write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改账户状态"
        )
    
    try:
        config_manager = ConfigurationManager()
        await config_manager.initialize()
        
        accounts_config = config_manager.get_config("accounts.yaml")
        
        if not accounts_config or "accounts" not in accounts_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="账户配置不存在"
            )
        
        account_found = False
        for account in accounts_config["accounts"]:
            if account["account_id"] == account_id:
                account_found = True
                account["enabled"] = True
                break
        
        if not account_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"账户 {account_id} 不存在"
            )
        
        await config_manager.save_config("accounts.yaml", accounts_config)
        await config_manager.close()
        
        logger.info("account_enabled", account_id=account_id, user=current_user.get("username"))
        
        return {"message": "账户已启用", "account_id": account_id, "enabled": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("enable_account_error", account_id=account_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启用账户失败: {str(e)}"
        )


@router.post("/{account_id}/disable")
async def disable_account(
    account_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    禁用账户
    Disable account
    
    需要管理员权限
    Requires admin permission
    """
    if not require_permission(current_user, "accounts", "write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改账户状态"
        )
    
    try:
        config_manager = ConfigurationManager()
        await config_manager.initialize()
        
        accounts_config = config_manager.get_config("accounts.yaml")
        
        if not accounts_config or "accounts" not in accounts_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="账户配置不存在"
            )
        
        account_found = False
        for account in accounts_config["accounts"]:
            if account["account_id"] == account_id:
                account_found = True
                account["enabled"] = False
                break
        
        if not account_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"账户 {account_id} 不存在"
            )
        
        await config_manager.save_config("accounts.yaml", accounts_config)
        await config_manager.close()
        
        logger.info("account_disabled", account_id=account_id, user=current_user.get("username"))
        
        return {"message": "账户已禁用", "account_id": account_id, "enabled": False}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("disable_account_error", account_id=account_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"禁用账户失败: {str(e)}"
        )


@router.get("/{account_id}/status", response_model=AccountStatusResponse)
async def get_account_status(
    account_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取账户实时状态
    Get account real-time status
    
    包括当前余额、权益、回撤、持仓等信息
    """
    try:
        # TODO: 从实际交易系统获取数据
        # 这里返回模拟数据
        
        return AccountStatusResponse(
            account_id=account_id,
            enabled=True,
            current_balance=10000.0,
            current_equity=9500.0,
            current_drawdown_percent=5.0,
            open_positions=3,
            daily_pnl=-500.0,
            daily_pnl_percent=-5.0,
            risk_status="warning",
            last_updated=datetime.now()
        )
        
    except Exception as e:
        logger.error("get_account_status_error", account_id=account_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取账户状态失败: {str(e)}"
        )

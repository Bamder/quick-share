from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.utils.response import created_response, bad_request_response, not_found_response, success_response
from app.utils.validation import validate_pickup_code
from app.extensions import get_db
from app.schemas.request import ReportRequest
from app.models.pickup_code import PickupCode
from app.models.report import Report

router = APIRouter(tags=["安全管理"])

@router.post("/reports")
async def report_file(request: ReportRequest, db: Session = Depends(get_db)):
    """
    举报违规文件
    """
    if not validate_pickup_code(request.code):
        return bad_request_response(msg="取件码格式错误")
    
    # 检查取件码是否存在
    pickup_code = db.query(PickupCode).filter(PickupCode.code == request.code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {request.code} 不存在")
    
    # 创建举报记录
    report = Report(
        code=request.code,
        reason=request.reason,
        reporter_ip=request.reporterInfo.ipAddress if request.reporterInfo else None,
        status="pending"
    )
    
    db.add(report)
    db.commit()
    db.refresh(report)
    
    return created_response(
        msg="举报已受理，感谢您的反馈",
        data={
            "reportId": report.id,
            "reportedAt": report.created_at.isoformat() + "Z",
            "status": report.status
        }
    )


@router.get("/reports/{report_id}")
async def get_report_status(report_id: int, db: Session = Depends(get_db)):
    """
    获取举报状态
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    
    if not report:
        return not_found_response(msg=f"举报记录 {report_id} 不存在")
    
    return success_response(data={
        "reportId": report.id,
        "code": report.code,
        "reason": report.reason,
        "status": report.status,
        "reportedAt": report.created_at.isoformat() + "Z",
        "updatedAt": report.updated_at.isoformat() + "Z" if report.updated_at else None
    })

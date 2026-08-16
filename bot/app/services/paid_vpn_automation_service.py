import inspect
from app.events import EventType,bus
from app.models.vpn_provisioning import ProvisioningSource,VPNProvisioningRequest
class PaidAutomationResult:
 def __init__(self,order_id,operation_key,status,vpn_key_id=None,error_code=None):self.order_id=order_id;self.operation_key=operation_key;self.status=status;self.vpn_key_id=vpn_key_id;self.error_code=error_code
class PaidVPNAutomationService:
 def __init__(self,*,db,provisioning_service,data_limit_service,lifecycle_service,notification_service=None):self.db=db;self.provisioning_service=provisioning_service;self.data_limit_service=data_limit_service;self.lifecycle_service=lifecycle_service;self.notification_service=notification_service
 async def provision_paid_order(self,*,order_id,user_id,package_id=None,requested_country=None,payment_reference=None):
  op=f'paid-order:{order_id}';req=VPNProvisioningRequest(user_id=user_id,source_type=ProvisioningSource.PAID_ORDER,order_id=order_id,package_id=package_id,preferred_country=requested_country,idempotency_key=op,request_reference=op,metadata={'payment_reference':payment_reference or 'terminal-paid'})
  r=await self.provisioning_service.provision(req,actor_user_id=user_id)
  if getattr(r,'is_failure',False):return PaidAutomationResult(order_id,op,'failed',error_code='provisioning_failed')
  s=getattr(r,'value',r);kid=int(getattr(s,'vpn_key_id',getattr(s,'key_id',0)))
  if kid<=0:return PaidAutomationResult(order_id,op,'failed',error_code='missing_vpn_key')
  r=await self.data_limit_service.apply_for_key(key_id=kid,actor_user_id=user_id,operation_id=op)
  if getattr(r,'is_failure',False):return PaidAutomationResult(order_id,op,'limit_failed',kid,'limit_failed')
  r=await self.lifecycle_service.activate_key(key_id=kid,actor_user_id=user_id)
  if getattr(r,'is_failure',False):return PaidAutomationResult(order_id,op,'activation_failed',kid,'activation_failed')
  emitted=bus.emit(EventType.VPN_AUTOMATION_READY,order_id=order_id,vpn_key_id=kid,operation_id=op)
  if inspect.isawaitable(emitted): await emitted
  return PaidAutomationResult(order_id,op,'ready',kid)
 async def handle_terminal_paid_event(self,**p):
  if p.get('payment_status') not in {'paid','completed'}:return None
  return await self.provision_paid_order(order_id=int(p['order_id']),user_id=int(p['user_id']),package_id=p.get('package_id'),requested_country=p.get('country'),payment_reference=p.get('payment_reference'))

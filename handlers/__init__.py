from aiogram import Router

from handlers import code, schedule, private, settings, group_bind

router = Router(name="main")
router.include_router(group_bind.router)
router.include_router(code.router)
router.include_router(schedule.router)
router.include_router(settings.router)
router.include_router(private.router)

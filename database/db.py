from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, insert, delete, func, update
from typing import AsyncGenerator, Optional, List
import asyncio

from config import DATABASE_URL
from database.models import (
    Base, Role, Permission, User, user_roles, role_permissions,
    Test, TestQuestion, TestResult, InternshipStage, Mentorship, TraineeTestAccess
)
from utils.logger import logger
import json
import os


engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    

    await create_initial_data()
    await update_role_permissions_for_existing_db()

async def create_initial_data():
    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(Role))
        count = result.scalar()
        if count == 0:
            roles = [
                Role(name="Стажер", description="Новый сотрудник на испытательном сроке"),
                Role(name="Сотрудник", description="Постоянный работник компании"),
                Role(name="Рекрутер", description="Специалист по подбору и управлению персоналом"),
                Role(name="Управляющий", description="Администратор с полным доступом к системе")
            ]
            session.add_all(roles)
            
            permissions = [
                Permission(name="view_profile", description="Просмотр собственного профиля"),
                Permission(name="edit_profile", description="Редактирование собственного профиля"),
                Permission(name="view_trainee_list", description="Просмотр списка Стажеров"),
                Permission(name="manage_trainees", description="Управление Стажерами"),
                Permission(name="manage_users", description="Управление пользователями"),
                Permission(name="manage_roles", description="Управление ролями"),
                Permission(name="create_tests", description="Создание тестов"),
                Permission(name="edit_tests", description="Редактирование тестов"),
                Permission(name="take_tests", description="Прохождение тестов"),
                Permission(name="view_test_results", description="Просмотр результатов тестов"),
                Permission(name="assign_mentors", description="Назначение наставников"),
                Permission(name="view_mentorship", description="Просмотр информации о наставничестве"),
                Permission(name="grant_test_access", description="Предоставление доступа к тестам")
            ]
            session.add_all(permissions)
            
            await session.commit()
            
            roles_query = await session.execute(select(Role))
            roles = roles_query.scalars().all()
            
            permissions_query = await session.execute(select(Permission))
            permissions = permissions_query.scalars().all()
            

            for role in roles:
                if role.name != "Управляющий":
                    for perm in permissions:
                        if perm.name in ["view_profile", "edit_profile"]:
                            stmt = insert(role_permissions).values(
                                role_id=role.id,
                                permission_id=perm.id
                            )
                            await session.execute(stmt)
            
            for role in roles:
                if role.name == "Рекрутер":
                    for perm in permissions:
                        if perm.name in ["view_trainee_list", "manage_trainees", "assign_mentors", "view_mentorship", "create_tests", "edit_tests", "view_test_results"]:
                            stmt = insert(role_permissions).values(
                                role_id=role.id,
                                permission_id=perm.id
                            )
                            await session.execute(stmt)
            
            for role in roles:
                if role.name == "Стажер":
                    for perm in permissions:
                        if perm.name in ["take_tests", "view_test_results", "view_mentorship"]:
                            stmt = insert(role_permissions).values(
                                role_id=role.id,
                                permission_id=perm.id
                            )
                            await session.execute(stmt)
            
            for role in roles:
                if role.name == "Сотрудник":
                    for perm in permissions:
                        if perm.name in ["view_test_results", "grant_test_access", "view_mentorship"]:
                            stmt = insert(role_permissions).values(
                                role_id=role.id,
                                permission_id=perm.id
                            )
                            await session.execute(stmt)
            
            for role in roles:
                if role.name == "Управляющий":
                    for perm in permissions:
                        stmt = insert(role_permissions).values(
                            role_id=role.id,
                            permission_id=perm.id
                        )
                        await session.execute(stmt)
            
            # Создание базовых этапов стажировки
            stages = [
                InternshipStage(name="Введение", description="Ознакомление с компанией", order_number=1),
                InternshipStage(name="Базовые навыки", description="Изучение основных процессов", order_number=2),
                InternshipStage(name="Практическое применение", description="Работа с реальными задачами", order_number=3),
                InternshipStage(name="Аттестация", description="Финальная проверка знаний", order_number=4)
            ]
            session.add_all(stages)
            
            await session.commit()
            logger.info("Начальные данные успешно созданы")


async def update_role_permissions_for_existing_db():
    """Обновление прав ролей для существующих баз данных"""
    async with async_session() as session:
        try:
            logger.info("Обновление прав доступа для ролей...")
            
            # Получаем роль Сотрудник
            employee_role = await get_role_by_name(session, "Сотрудник")
            if employee_role:
                # Удаляем права create_tests и edit_tests у Сотрудника
                await remove_permission_from_role(session, employee_role.id, "create_tests")
                await remove_permission_from_role(session, employee_role.id, "edit_tests")
                logger.info("Удалены права create_tests и edit_tests у роли Сотрудник")
            
            logger.info("Обновление прав доступа завершено")
        except Exception as e:
            logger.error(f"Ошибка обновления прав доступа: {e}")


async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> Optional[User]:
    try:
        result = await session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения пользователя по tg_id {tg_id}: {e}")
        return None


async def check_phone_exists(session: AsyncSession, phone_number: str) -> bool:
    result = await session.execute(
        select(func.count()).select_from(User).where(User.phone_number == phone_number)
    )
    count = result.scalar()
    return count > 0


async def create_user(session: AsyncSession, user_data: dict, role_name: str, bot=None) -> User:
    try:
        user = User(
            tg_id=user_data['tg_id'],
            username=user_data.get('username'),
            full_name=user_data['full_name'],
            phone_number=user_data['phone_number']
        )
        session.add(user)
        await session.flush()
        
        role_result = await session.execute(
            select(Role).where(Role.name == role_name)
        )
        role = role_result.scalar_one()

        stmt = insert(user_roles).values(
            user_id=user.id,
            role_id=role.id
        )
        await session.execute(stmt)
        
        await session.commit()
        
        # Отправляем уведомления рекрутерам если создан новый стажёр
        if role_name == "Стажер" and bot:
            await send_notification_about_new_trainee_registration(session, bot, user.id)
        
        return user
    except Exception as e:
        logger.error(f"Ошибка создания пользователя: {e}")
        await session.rollback()
        raise


async def check_user_permission(session: AsyncSession, user_id: int, permission_name: str) -> bool:
    stmt = select(func.count()).select_from(User).join(
        user_roles, User.id == user_roles.c.user_id
    ).join(
        role_permissions, user_roles.c.role_id == role_permissions.c.role_id
    ).join(
        Permission, role_permissions.c.permission_id == Permission.id
    ).where(
        User.id == user_id,
        Permission.name == permission_name
    )
    
    result = await session.execute(stmt)
    count = result.scalar()
    return count > 0


async def get_user_roles(session: AsyncSession, user_id: int) -> List[Role]:
    try:
        stmt = select(Role).join(
            user_roles, Role.id == user_roles.c.role_id
        ).where(
            user_roles.c.user_id == user_id
        )
        
        result = await session.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения ролей для пользователя {user_id}: {e}")
        return []


async def add_user_role(session: AsyncSession, user_id: int, role_name: str) -> bool:
    try:
        role_result = await session.execute(
            select(Role).where(Role.name == role_name)
        )
        role = role_result.scalar_one_or_none()
        
        if not role:
            return False
        
        check_stmt = select(func.count()).select_from(user_roles).where(
            user_roles.c.user_id == user_id,
            user_roles.c.role_id == role.id
        )
        check_result = await session.execute(check_stmt)
        
        has_role = check_result.scalar()
        if has_role > 0:
            return True
        
        stmt = insert(user_roles).values(
            user_id=user_id,
            role_id=role.id
        )
        await session.execute(stmt)
        
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления роли пользователю {user_id}: {e}")
        await session.rollback()
        return False


async def remove_user_role(session: AsyncSession, user_id: int, role_name: str) -> bool:
    try:
        role_result = await session.execute(
            select(Role).where(Role.name == role_name)
        )
        role = role_result.scalar_one_or_none()
        
        if not role:
            return False
        
        stmt = delete(user_roles).where(
            user_roles.c.user_id == user_id,
            user_roles.c.role_id == role.id
        )
        await session.execute(stmt)
        
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления роли у пользователя {user_id}: {e}")
        await session.rollback()
        return False


async def get_all_users(session: AsyncSession) -> List[User]:
    """ Получение списка всех пользователей"""

    try:
        result = await session.execute(select(User).order_by(User.registration_date.desc()))
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения всех пользователей: {e}")
        return []


async def get_all_trainees(session: AsyncSession) -> List[User]:
    """Получение списка всех Стажеров"""

    try:
        stmt = select(User).join(
            user_roles, User.id == user_roles.c.user_id
        ).join(
            Role, user_roles.c.role_id == Role.id
        ).where(
            Role.name == "Стажер"
        ).order_by(User.registration_date.desc())
        
        result = await session.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения всех стажёров: {e}")
        return []


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    """Получение пользователя по его ID """

    try:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения пользователя по ID {user_id}: {e}")
        return None


async def update_user_profile(session: AsyncSession, user_id: int, update_data: dict) -> bool:
    """Обновление профиля пользователя"""

    try:
        stmt = update(User).where(User.id == user_id)
        
        valid_fields = ['full_name', 'phone_number', 'username', 'is_active']
        update_values = {k: v for k, v in update_data.items() if k in valid_fields}
        
        if not update_values:
            return False
        
        stmt = stmt.values(**update_values)
        await session.execute(stmt)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления профиля пользователя {user_id}: {e}")
        await session.rollback()
        return False


async def get_users_by_role(session: AsyncSession, role_name: str) -> List[User]:
    """Получение всех пользователей с указанной ролью """
    try:
        stmt = select(User).join(
            user_roles, User.id == user_roles.c.user_id
        ).join(
            Role, user_roles.c.role_id == Role.id
        ).where(
            Role.name == role_name
        ).order_by(User.full_name)
        
        result = await session.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения пользователей с ролью {role_name}: {e}")
        return []

async def delete_user(session: AsyncSession, user_id: int) -> bool:
    """Удаление пользователя из системы"""

    try:
        await session.execute(
            delete(user_roles).where(user_roles.c.user_id == user_id)
        )
        
        await session.execute(
            delete(User).where(User.id == user_id)
        )
        
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления пользователя {user_id}: {e}")
        await session.rollback()
        return False


async def get_all_roles(session: AsyncSession) -> List[Role]:
    """Получение списка всех ролей"""

    try:
        result = await session.execute(select(Role).order_by(Role.name))
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения всех ролей: {e}")
        return []


async def get_all_permissions(session: AsyncSession) -> List[Permission]:
    """Получение списка всех прав доступа """

    try:
        result = await session.execute(select(Permission).order_by(Permission.name))
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения всех прав: {e}")
        return []

async def get_role_permissions(session: AsyncSession, role_id: int) -> List[Permission]:
    """Получение всех прав для указанной роли"""

    try:
        stmt = select(Permission).join(
            role_permissions, Permission.id == role_permissions.c.permission_id
        ).where(
            role_permissions.c.role_id == role_id
        ).order_by(Permission.name)
        
        result = await session.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения прав для роли {role_id}: {e}")
        return []

async def add_permission_to_role(session: AsyncSession, role_id: int, permission_name: str) -> bool:
    """Добавление права роли"""

    try:
        perm_result = await session.execute(
            select(Permission).where(Permission.name == permission_name)
        )
        permission = perm_result.scalar_one_or_none()
        
        if not permission:
            logger.error(f"Право {permission_name} не найдено")
            return False
        
        check_stmt = select(func.count()).select_from(role_permissions).where(
            role_permissions.c.role_id == role_id,
            role_permissions.c.permission_id == permission.id
        )
        check_result = await session.execute(check_stmt)
        
        has_permission = check_result.scalar()
        if has_permission > 0:
            logger.info(f"Роль {role_id} уже имеет право {permission_name}")
            return True
        
        stmt = insert(role_permissions).values(
            role_id=role_id,
            permission_id=permission.id
        )
        await session.execute(stmt)
        
        await session.commit()
        logger.info(f"Право {permission_name} добавлено роли {role_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления права {permission_name} к роли {role_id}: {e}")
        await session.rollback()
        return False

async def remove_permission_from_role(session: AsyncSession, role_id: int, permission_name: str) -> bool:
    """Удаление права у роли"""

    try:
        perm_result = await session.execute(
            select(Permission).where(Permission.name == permission_name)
        )
        permission = perm_result.scalar_one_or_none()
        
        if not permission:
            logger.error(f"Право {permission_name} не найдено")
            return False
        
        stmt = delete(role_permissions).where(
            role_permissions.c.role_id == role_id,
            role_permissions.c.permission_id == permission.id
        )
        await session.execute(stmt)
        
        await session.commit()
        logger.info(f"Право {permission_name} удалено у роли {role_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления права {permission_name} у роли {role_id}: {e}")
        await session.rollback()
        return False

async def create_new_permission(session: AsyncSession, name: str, description: str) -> Optional[Permission]:
    """Создание нового права доступа"""
    try:
        check_stmt = select(func.count()).select_from(Permission).where(Permission.name == name)
        check_result = await session.execute(check_stmt)
        
        exists = check_result.scalar()
        if exists > 0:
            logger.error(f"Право с именем {name} уже существует")
            return None
        
        permission = Permission(
            name=name,
            description=description
        )
        session.add(permission)
        await session.commit()
        
        logger.info(f"Создано новое право: {name}")
        return permission
    except Exception as e:
        logger.error(f"Ошибка создания нового права {name}: {e}")
        await session.rollback()
        return None

async def get_role_by_name(session: AsyncSession, role_name: str) -> Optional[Role]:
    """Получение роли по имени"""

    try:
        result = await session.execute(select(Role).where(Role.name == role_name))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения роли по имени {role_name}: {e}")
        return None

async def get_permission_by_name(session: AsyncSession, permission_name: str) -> Optional[Permission]:
    """Получение права по имени"""

    try:
        result = await session.execute(select(Permission).where(Permission.name == permission_name))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения права по имени {permission_name}: {e}")
        return None


# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ТЕСТАМИ
# =================================

async def create_test(session: AsyncSession, test_data: dict) -> Optional[Test]:
    """Создание нового теста с валидацией"""
    try:
        # Валидация обязательных полей
        if not test_data.get('name') or len(test_data['name'].strip()) < 3:
            logger.error("Название теста должно содержать не менее 3 символов")
            return None
        
        if not test_data.get('creator_id'):
            logger.error("Не указан создатель теста")
            return None
        
        # Проверка существования создателя
        creator_exists = await session.execute(
            select(User).where(User.id == test_data['creator_id'])
        )
        if not creator_exists.scalar_one_or_none():
            logger.error(f"Создатель с ID {test_data['creator_id']} не найден")
            return None
        
        # Валидация материалов (если указана ссылка)
        material_link = test_data.get('material_link')
        if material_link and not (material_link.startswith('http://') or material_link.startswith('https://')):
            logger.warning(f"Ссылка на материалы не содержит протокол: {material_link}")
        
        test = Test(
            name=test_data['name'].strip(),
            description=test_data.get('description', '').strip() if test_data.get('description') else None,
            threshold_score=max(1, test_data.get('threshold_score', 1)),
            max_score=max(0, test_data.get('max_score', 0)),
            material_link=material_link,
            material_file_path=test_data.get('material_file_path'),
            stage_id=test_data.get('stage_id'),
            creator_id=test_data['creator_id']
        )
        session.add(test)
        await session.flush()
        await session.commit()
        logger.info(f"Тест '{test.name}' создан успешно (ID: {test.id})")
        return test
    except Exception as e:
        logger.error(f"Ошибка создания теста: {e}")
        await session.rollback()
        return None

async def get_test_by_id(session: AsyncSession, test_id: int) -> Optional[Test]:
    """Получение теста по ID"""
    try:
        result = await session.execute(select(Test).where(Test.id == test_id))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения теста {test_id}: {e}")
        return None

async def get_tests_by_creator(session: AsyncSession, creator_id: int) -> List[Test]:
    """Получение всех тестов, созданных пользователем"""
    try:
        result = await session.execute(
            select(Test).where(Test.creator_id == creator_id, Test.is_active == True)
            .order_by(Test.created_date.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения тестов пользователя {creator_id}: {e}")
        return []

async def get_all_active_tests(session: AsyncSession) -> List[Test]:
    """Получение всех активных тестов"""
    try:
        result = await session.execute(
            select(Test).where(Test.is_active == True)
            .order_by(Test.created_date.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения всех тестов: {e}")
        return []

async def update_test(session: AsyncSession, test_id: int, update_data: dict) -> bool:
    """Обновление теста"""
    try:
        valid_fields = ['name', 'description', 'threshold_score', 'max_score', 
                       'material_link', 'material_file_path', 'stage_id', 
                       'shuffle_questions', 'max_attempts']
        update_values = {k: v for k, v in update_data.items() if k in valid_fields}
        
        if not update_values:
            return False
        
        stmt = update(Test).where(Test.id == test_id).values(**update_values)
        await session.execute(stmt)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления теста {test_id}: {e}")
        await session.rollback()
        return False

async def delete_test(session: AsyncSession, test_id: int) -> bool:
    """Удаление теста (мягкое удаление)"""
    try:
        stmt = update(Test).where(Test.id == test_id).values(is_active=False)
        await session.execute(stmt)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления теста {test_id}: {e}")
        await session.rollback()
        return False

# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ВОПРОСАМИ
# =================================

async def add_question_to_test(session: AsyncSession, question_data: dict) -> Optional[TestQuestion]:
    """Добавление вопроса к тесту с проверкой на уникальность"""
    try:
        # Проверка на уникальность текста вопроса в рамках теста
        existing_question = await session.execute(
            select(TestQuestion).where(
                TestQuestion.test_id == question_data['test_id'],
                TestQuestion.question_text == question_data['question_text']
            )
        )
        if existing_question.scalar_one_or_none():
            logger.warning(f"Попытка добавить дублирующийся вопрос в тест {question_data['test_id']}")
            return None # или можно вернуть ошибку

        question = TestQuestion(
            test_id=question_data['test_id'],
            question_number=question_data['question_number'],
            question_type=question_data['question_type'],
            question_text=question_data['question_text'],
            options=question_data.get('options'),
            correct_answer=json.dumps(question_data['correct_answer']) if isinstance(question_data['correct_answer'], list) else question_data['correct_answer'],
            points=question_data.get('points', 1),
            penalty_points=question_data.get('penalty_points', 0)
        )
        session.add(question)
        await session.flush()
        
        # Обновляем максимальный балл теста
        await update_test_max_score(session, question_data['test_id'])
        
        await session.commit()
        return question
    except Exception as e:
        logger.error(f"Ошибка добавления вопроса: {e}")
        await session.rollback()
        return None

async def get_test_questions(session: AsyncSession, test_id: int) -> List[TestQuestion]:
    """Получение всех вопросов теста"""
    try:
        result = await session.execute(
            select(TestQuestion).where(TestQuestion.test_id == test_id)
            .order_by(TestQuestion.question_number)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения вопросов теста {test_id}: {e}")
        return []

async def update_question(session: AsyncSession, question_id: int, update_data: dict) -> bool:
    """Обновление вопроса"""
    try:
        valid_fields = ['question_text', 'correct_answer', 'points']
        update_values = {k: v for k, v in update_data.items() if k in valid_fields}
        
        if not update_values:
            return False
        
        # Получаем старую информацию о вопросе для обновления максимального балла
        old_question = await session.execute(
            select(TestQuestion).where(TestQuestion.id == question_id)
        )
        old_question = old_question.scalar_one_or_none()
        
        if not old_question:
            return False
        
        stmt = update(TestQuestion).where(TestQuestion.id == question_id).values(**update_values)
        await session.execute(stmt)
        
        # Обновляем максимальный балл теста
        await update_test_max_score(session, old_question.test_id)
        
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления вопроса {question_id}: {e}")
        await session.rollback()
        return False

async def delete_question(session: AsyncSession, question_id: int) -> bool:
    """Удаление вопроса"""
    try:
        # Получаем информацию о вопросе для обновления максимального балла
        question = await session.execute(
            select(TestQuestion).where(TestQuestion.id == question_id)
        )
        question = question.scalar_one_or_none()
        
        if not question:
            return False
        
        test_id = question.test_id
        
        await session.execute(delete(TestQuestion).where(TestQuestion.id == question_id))
        
        # Обновляем максимальный балл теста
        await update_test_max_score(session, test_id)
        
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления вопроса {question_id}: {e}")
        await session.rollback()
        return False

async def update_test_max_score(session: AsyncSession, test_id: int):
    """Обновление максимального балла теста на основе вопросов"""
    try:
        result = await session.execute(
            select(func.sum(TestQuestion.points)).where(TestQuestion.test_id == test_id)
        )
        max_score = result.scalar() or 0
        
        stmt = update(Test).where(Test.id == test_id).values(max_score=max_score)
        await session.execute(stmt)
    except Exception as e:
        logger.error(f"Ошибка обновления максимального балла теста {test_id}: {e}")

# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ЭТАПАМИ СТАЖИРОВКИ
# =================================

async def get_all_stages(session: AsyncSession) -> List[InternshipStage]:
    """Получение всех этапов стажировки"""
    try:
        result = await session.execute(
            select(InternshipStage).where(InternshipStage.is_active == True)
            .order_by(InternshipStage.order_number)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения этапов стажировки: {e}")
        return []

async def get_stage_by_id(session: AsyncSession, stage_id: int) -> Optional[InternshipStage]:
    """Получение этапа по ID"""
    try:
        result = await session.execute(select(InternshipStage).where(InternshipStage.id == stage_id))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения этапа {stage_id}: {e}")
        return None

# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С НАСТАВНИЧЕСТВОМ
# =================================

async def assign_mentor(session: AsyncSession, mentor_id: int, trainee_id: int, assigned_by_id: int, bot=None) -> Optional[Mentorship]:
    """Назначение наставника стажеру с полной валидацией"""
    try:
        # Валидация входных данных
        if not all([mentor_id, trainee_id, assigned_by_id]):
            logger.error("Все ID должны быть указаны для назначения наставника")
            return None
        
        if mentor_id == trainee_id:
            logger.error("Наставник не может быть наставником самому себе")
            return None
        
        # Проверяем существование пользователей
        mentor = await session.execute(select(User).where(User.id == mentor_id, User.is_active == True))
        mentor = mentor.scalar_one_or_none()
        if not mentor:
            logger.error(f"Наставник с ID {mentor_id} не найден или неактивен")
            return None
        
        trainee = await session.execute(select(User).where(User.id == trainee_id, User.is_active == True))
        trainee = trainee.scalar_one_or_none()
        if not trainee:
            logger.error(f"Стажер с ID {trainee_id} не найден или неактивен")
            return None
        
        assigned_by = await session.execute(select(User).where(User.id == assigned_by_id, User.is_active == True))
        if not assigned_by.scalar_one_or_none():
            logger.error(f"Пользователь назначающий с ID {assigned_by_id} не найден")
            return None
        
        # Проверяем, что наставник имеет подходящую роль
        mentor_roles = await get_user_roles(session, mentor_id)
        role_names = [role.name for role in mentor_roles]
        if not any(role in ["Сотрудник", "Управляющий"] for role in role_names):
            logger.error(f"Пользователь {mentor_id} не может быть наставником (неподходящая роль)")
            return None
        
        # Проверяем, что стажер имеет роль стажера
        trainee_roles = await get_user_roles(session, trainee_id)
        trainee_role_names = [role.name for role in trainee_roles]
        if "Стажер" not in trainee_role_names:
            logger.error(f"Пользователь {trainee_id} не является стажером")
            return None
        
        # Проверяем, нет ли уже активного наставничества
        existing = await session.execute(
            select(Mentorship).where(
                Mentorship.trainee_id == trainee_id,
                Mentorship.is_active == True
            )
        )
        existing_mentorship = existing.scalar_one_or_none()
        
        if existing_mentorship:
            logger.warning(f"Стажер {trainee.full_name} уже имеет наставника. Переназначение...")
            # Деактивируем старое наставничество
            stmt = update(Mentorship).where(Mentorship.id == existing_mentorship.id).values(is_active=False)
            await session.execute(stmt)
        
        mentorship = Mentorship(
            mentor_id=mentor_id,
            trainee_id=trainee_id,
            assigned_by_id=assigned_by_id
        )
        session.add(mentorship)
        await session.commit()
        logger.info(f"Наставник {mentor.full_name} назначен стажеру {trainee.full_name}")
        
        # Отправляем уведомление стажёру о назначении наставника
        if bot:
            await send_notification_about_mentor_assignment(
                session, bot, trainee_id, mentor_id, assigned_by_id
            )
        
        # Отправляем уведомление наставнику о назначении стажёра
        if bot:
            await send_notification_about_new_trainee(
                session, bot, mentor_id, trainee_id, assigned_by_id
            )
        
        return mentorship
    except Exception as e:
        logger.error(f"Ошибка назначения наставника: {e}")
        await session.rollback()
        return None

async def get_mentor_trainees(session: AsyncSession, mentor_id: int) -> List[User]:
    """Получение списка стажеров у наставника"""
    try:
        result = await session.execute(
            select(User).join(
                Mentorship, User.id == Mentorship.trainee_id
            ).where(
                Mentorship.mentor_id == mentor_id,
                Mentorship.is_active == True
            ).order_by(User.full_name)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения стажеров наставника {mentor_id}: {e}")
        return []

async def get_trainee_mentor(session: AsyncSession, trainee_id: int) -> Optional[User]:
    """Получение наставника стажера"""
    try:
        result = await session.execute(
            select(User).join(
                Mentorship, User.id == Mentorship.mentor_id
            ).where(
                Mentorship.trainee_id == trainee_id,
                Mentorship.is_active == True
            )
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения наставника стажера {trainee_id}: {e}")
        return None

async def get_unassigned_trainees(session: AsyncSession) -> List[User]:
    """Получение списка стажеров без наставника"""
    try:
        result = await session.execute(
            select(User).join(
                user_roles, User.id == user_roles.c.user_id
            ).join(
                Role, user_roles.c.role_id == Role.id
            ).where(
                Role.name == "Стажер",
                ~User.id.in_(
                    select(Mentorship.trainee_id).where(Mentorship.is_active == True)
                )
            ).order_by(User.full_name)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения стажеров без наставника: {e}")
        return []

async def get_available_mentors(session: AsyncSession) -> List[User]:
    """Получение списка пользователей, которые могут быть наставниками"""
    try:
        result = await session.execute(
            select(User).join(
                user_roles, User.id == user_roles.c.user_id
            ).join(
                Role, user_roles.c.role_id == Role.id
            ).where(
                Role.name.in_(["Сотрудник", "Управляющий"])
            ).order_by(User.full_name)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения доступных наставников: {e}")
        return []

# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ДОСТУПОМ К ТЕСТАМ
# =================================

async def grant_test_access(session: AsyncSession, trainee_id: int, test_id: int, granted_by_id: int, bot=None) -> bool:
    """Предоставление доступа к тесту стажеру"""
    try:
        # Проверяем, нет ли уже доступа
        existing = await session.execute(
            select(TraineeTestAccess).where(
                TraineeTestAccess.trainee_id == trainee_id,
                TraineeTestAccess.test_id == test_id,
                TraineeTestAccess.is_active == True
            )
        )
        existing_access = existing.scalar_one_or_none()
        
        # Если доступа еще нет - создаем новый
        if not existing_access:
            access = TraineeTestAccess(
                trainee_id=trainee_id,
                test_id=test_id,
                granted_by_id=granted_by_id
            )
            session.add(access)
            await session.commit()
            logger.info(f"Создан новый доступ к тесту {test_id} для стажёра {trainee_id}")
        else:
            logger.info(f"Доступ к тесту {test_id} для стажёра {trainee_id} уже существует - отправляем повторное уведомление")
        
        # Отправляем уведомление стажеру ВСЕГДА (и при новом доступе, и при повторном назначении)
        if bot:
            await send_notification_about_new_test(session, bot, trainee_id, test_id, granted_by_id)
        
        return True
    except Exception as e:
        logger.error(f"Ошибка предоставления доступа к тесту: {e}")
        await session.rollback()
        return False

async def get_trainee_available_tests(session: AsyncSession, trainee_id: int) -> List[Test]:
    """Получение доступных тестов для стажера"""
    try:
        result = await session.execute(
            select(Test).join(
                TraineeTestAccess, Test.id == TraineeTestAccess.test_id
            ).where(
                TraineeTestAccess.trainee_id == trainee_id,
                TraineeTestAccess.is_active == True,
                Test.is_active == True
            ).order_by(Test.created_date)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения доступных тестов для стажера {trainee_id}: {e}")
        return []

async def revoke_test_access(session: AsyncSession, trainee_id: int, test_id: int) -> bool:
    """Отзыв доступа к тесту"""
    try:
        stmt = update(TraineeTestAccess).where(
            TraineeTestAccess.trainee_id == trainee_id,
            TraineeTestAccess.test_id == test_id
        ).values(is_active=False)
        await session.execute(stmt)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка отзыва доступа к тесту: {e}")
        await session.rollback()
        return False

# =================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С РЕЗУЛЬТАТАМИ ТЕСТОВ
# =================================

async def save_test_result(session: AsyncSession, result_data: dict) -> Optional[TestResult]:
    """Сохранение результата прохождения теста"""
    try:
        test_result = TestResult(
            user_id=result_data['user_id'],
            test_id=result_data['test_id'],
            score=result_data['score'],
            max_possible_score=result_data['max_possible_score'],
            is_passed=result_data['is_passed'],
            start_time=result_data['start_time'],
            end_time=result_data['end_time'],
            answers=json.dumps(result_data.get('answers', {}), ensure_ascii=False),
            answers_details=result_data.get('answers_details', []),
            wrong_answers=result_data.get('wrong_answers', [])
        )
        session.add(test_result)
        await session.commit()
        logger.info(f"Результат теста сохранен для пользователя {result_data['user_id']}, тест {result_data['test_id']}")
        return test_result
    except Exception as e:
        logger.error(f"Ошибка сохранения результата теста: {e}")
        await session.rollback()
        return None

async def get_user_test_results(session: AsyncSession, user_id: int) -> List[TestResult]:
    """Получение результатов тестов пользователя"""
    try:
        result = await session.execute(
            select(TestResult).where(TestResult.user_id == user_id)
            .order_by(TestResult.created_date.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения результатов тестов пользователя {user_id}: {e}")
        return []

async def get_test_results_summary(session: AsyncSession, test_id: int) -> List[TestResult]:
    """Получение сводки результатов по тесту"""
    try:
        result = await session.execute(
            select(TestResult).where(TestResult.test_id == test_id)
            .order_by(TestResult.score.desc())
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка получения сводки результатов теста {test_id}: {e}")
        return []

async def check_test_already_passed(session: AsyncSession, user_id: int, test_id: int) -> bool:
    """Проверка, проходил ли пользователь тест"""
    try:
        result = await session.execute(
            select(func.count()).select_from(TestResult).where(
                TestResult.user_id == user_id,
                TestResult.test_id == test_id
            )
        )
        count = result.scalar()
        return count > 0
    except Exception as e:
        logger.error(f"Ошибка проверки прохождения теста: {e}")
        return False

async def check_test_access(session: AsyncSession, user_id: int, test_id: int) -> bool:
    """Проверка доступа пользователя к тесту"""
    try:
        result = await session.execute(
            select(TraineeTestAccess).where(
                TraineeTestAccess.trainee_id == user_id,
                TraineeTestAccess.test_id == test_id,
                TraineeTestAccess.is_active == True
            )
        )
        access = result.scalar_one_or_none()
        return access is not None
    except Exception as e:
        logger.error(f"Ошибка проверки доступа к тесту: {e}")
        return False

async def get_user_test_result(session: AsyncSession, user_id: int, test_id: int) -> Optional[TestResult]:
    """Получение результата конкретного теста пользователя"""
    try:
        result = await session.execute(
            select(TestResult).where(
                TestResult.user_id == user_id,
                TestResult.test_id == test_id
            ).order_by(TestResult.created_date.desc())
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения результата теста пользователя: {e}")
        return None

async def get_user_test_attempts_count(session: AsyncSession, user_id: int, test_id: int) -> int:
    """Подсчет количества попыток прохождения теста пользователем"""
    try:
        result = await session.execute(
            select(func.count()).select_from(TestResult).where(
                TestResult.user_id == user_id,
                TestResult.test_id == test_id
            )
        )
        return result.scalar() or 0
    except Exception as e:
        logger.error(f"Ошибка подсчета попыток теста: {e}")
        return 0

async def can_user_take_test(session: AsyncSession, user_id: int, test_id: int) -> tuple[bool, str]:
    """
    Проверяет, может ли пользователь пройти тест (с учетом ограничений попыток)
    Возвращает: (можно_ли_проходить, сообщение_об_ошибке)
    """
    try:
        # Получаем тест
        test = await get_test_by_id(session, test_id)
        if not test:
            return False, "Тест не найден"
        
        # Если max_attempts = 0, то бесконечно попыток
        if test.max_attempts == 0:
            return True, ""
        
        # Подсчитываем текущее количество попыток
        attempts_count = await get_user_test_attempts_count(session, user_id, test_id)
        
        if attempts_count >= test.max_attempts:
            return False, f"Исчерпан лимит попыток ({attempts_count}/{test.max_attempts})"
        
        return True, ""
    except Exception as e:
        logger.error(f"Ошибка проверки возможности прохождения теста: {e}")
        return False, "Ошибка проверки доступа"

async def get_question_analytics(session: AsyncSession, question_id: int) -> dict:
    """Собирает и возвращает реальную аналитику по конкретному вопросу."""
    
    # Находим все результаты, где есть информация по данному вопросу
    all_results_query = await session.execute(
        select(TestResult).where(TestResult.answers_details.isnot(None))
    )
    all_results = all_results_query.scalars().all()
    
    relevant_answers = []
    for result in all_results:
        # answers_details - это список словарей
        for answer_detail in result.answers_details:
            if answer_detail.get('question_id') == question_id:
                relevant_answers.append(answer_detail)

    if not relevant_answers:
        return {"total_answers": 0, "correct_answers": 0, "avg_time_seconds": 0}

    total_answers = len(relevant_answers)
    correct_answers = sum(1 for ans in relevant_answers if ans.get('is_correct'))
    total_time = sum(ans.get('time_spent', 0) for ans in relevant_answers)
    
    return {
        "total_answers": total_answers,
        "correct_answers": correct_answers,
        "avg_time_seconds": total_time / total_answers if total_answers > 0 else 0
    }

async def create_initial_admin_with_token(session: AsyncSession, admin_data: dict, init_token: str) -> bool:
    """Создание администратора с проверкой токена инициализации"""
    import os
    
    # Поддержка множественных токенов через запятую
    admin_tokens_str = os.getenv("ADMIN_INIT_TOKENS", os.getenv("ADMIN_INIT_TOKEN", ""))
    
    # Добавляем детальное логирование для отладки
    logger.info(f"DEBUG: Попытка создания админа с токеном: '{init_token}'")
    logger.info(f"DEBUG: Переменная ADMIN_INIT_TOKENS: '{os.getenv('ADMIN_INIT_TOKENS')}'")
    logger.info(f"DEBUG: Переменная ADMIN_INIT_TOKEN: '{os.getenv('ADMIN_INIT_TOKEN')}'")
    logger.info(f"DEBUG: Итоговая строка токенов: '{admin_tokens_str}'")
    
    if not admin_tokens_str:
        logger.error("Не настроены токены инициализации администратора")
        return False
    
    # Разбираем токены
    valid_tokens = [token.strip() for token in admin_tokens_str.split(",") if token.strip()]
    logger.info(f"DEBUG: Валидные токены: {valid_tokens}")
    logger.info(f"DEBUG: Введенный токен: '{init_token}'")
    logger.info(f"DEBUG: Токен в списке валидных: {init_token in valid_tokens}")
    
    if init_token not in valid_tokens:
        logger.error(f"Неверный токен инициализации администратора. Ожидался один из: {valid_tokens}")
        return False
    
    # Проверяем лимит управляющих (по умолчанию максимум 5)
    max_admins = int(os.getenv("MAX_ADMINS", "5"))
    existing_managers = await get_users_by_role(session, "Управляющий")
    logger.info(f"DEBUG: Существующих админов: {len(existing_managers)}, лимит: {max_admins}")
    
    if len(existing_managers) >= max_admins:
        logger.error(f"Достигнут лимит управляющих ({max_admins})")
        return False
    
    try:
        user = User(
            tg_id=admin_data['tg_id'],
            username=admin_data.get('username'),
            full_name=admin_data['full_name'],
            phone_number=admin_data['phone_number']
        )
        session.add(user)
        await session.flush()
        
        role_result = await session.execute(
            select(Role).where(Role.name == "Управляющий")
        )
        role = role_result.scalar_one()

        stmt = insert(user_roles).values(
            user_id=user.id,
            role_id=role.id
        )
        await session.execute(stmt)
        
        await session.commit()
        logger.info(f"Первый администратор создан: {user.full_name}")
        return True
    except Exception as e:
        logger.error(f"Ошибка создания администратора: {e}")
        await session.rollback()
        return False

# =================================
# ФУНКЦИИ ДЛЯ УВЕДОМЛЕНИЙ
# =================================

async def send_notification_about_new_test(session: AsyncSession, bot, trainee_id: int, test_id: int, granted_by_id: int):
    """Отправка уведомления стажеру о назначении нового теста"""
    try:
        # Получаем данные о стажере
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            logger.error(f"Стажер с ID {trainee_id} не найден")
            return False
            
        # Получаем данные о тесте
        test = await get_test_by_id(session, test_id)
        if not test:
            logger.error(f"Тест с ID {test_id} не найден")
            return False
            
        # Получаем данные о наставнике
        mentor = await get_user_by_id(session, granted_by_id)
        if not mentor:
            logger.error(f"Наставник с ID {granted_by_id} не найден")
            return False
            
        # Получаем название этапа, если есть
        stage_name = None
        if test.stage_id:
            stage = await get_stage_by_id(session, test.stage_id)
            if stage:
                stage_name = stage.name
        
        await send_test_notification(
            bot=bot,
            trainee_tg_id=trainee.tg_id,
            test_name=test.name,
            mentor_name=mentor.full_name,
            test_description=test.description,
            stage_name=stage_name,
            test_id=test_id
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о новом тесте: {e}")
        return False

async def send_notification_about_mentor_assignment(session: AsyncSession, bot, trainee_id: int, mentor_id: int, assigned_by_id: int):
    """Отправка уведомления стажеру о назначении наставника"""
    try:
        # Получаем данные о стажере
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            logger.error(f"Стажер с ID {trainee_id} не найден")
            return False
            
        # Получаем данные о наставнике
        mentor = await get_user_by_id(session, mentor_id)
        if not mentor:
            logger.error(f"Наставник с ID {mentor_id} не найден")
            return False
            
        # Получаем данные о том, кто назначил
        assigned_by = await get_user_by_id(session, assigned_by_id)
        if not assigned_by:
            logger.error(f"Пользователь назначивший с ID {assigned_by_id} не найден")
            return False
        
        await send_mentor_assignment_notification(
            bot=bot,
            trainee_tg_id=trainee.tg_id,
            mentor_name=mentor.full_name,
            mentor_phone=mentor.phone_number,
            mentor_username=mentor.username,
            assigned_by_name=assigned_by.full_name
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о назначении наставника: {e}")
        return False

async def send_test_notification(bot, trainee_tg_id: int, test_name: str, mentor_name: str, test_description: str = None, stage_name: str = None, test_id: int = None):
    """Отправка уведомления стажеру о назначении нового теста"""
    try:
        stage_info = f"\n🎯 <b>Этап:</b> {stage_name}" if stage_name else ""
        description_info = f"\n📝 <b>Описание:</b> {test_description}" if test_description else ""
        
        notification_text = f"""🔔 <b>Тест для прохождения!</b>

📋 <b>Название:</b> {test_name}{stage_info}{description_info}

👨‍🏫 <b>Наставник:</b> {mentor_name}

💡 <b>Что дальше?</b>
• Изучите материалы к тесту (если есть)
• Нажмите кнопку ниже для быстрого перехода
• Или откройте меню "Доступные тесты"

🎯 <b>Удачи в прохождении!</b>"""

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        # Создаем клавиатуру с кнопкой быстрого перехода к тесту
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Перейти к тесту", callback_data=f"take_test:{test_id}")],
            [InlineKeyboardButton(text="📋 Все доступные тесты", callback_data="available_tests")]
        ]) if test_id else None
        
        await bot.send_message(
            chat_id=trainee_tg_id,
            text=notification_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        logger.info(f"Уведомление о тесте '{test_name}' отправлено стажеру {trainee_tg_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления стажеру {trainee_tg_id}: {e}")
        return False

async def send_mentor_assignment_notification(bot, trainee_tg_id: int, mentor_name: str, mentor_phone: str, mentor_username: str = None, assigned_by_name: str = None):
    """Отправка уведомления стажеру о назначении наставника"""
    try:
        # Формируем контактную информацию наставника
        contact_info = f"📞 <b>Телефон:</b> {mentor_phone}"
        if mentor_username:
            contact_info += f"\n📧 <b>Telegram:</b> @{mentor_username}"
        else:
            contact_info += f"\n📧 <b>Telegram:</b> не указан"
        
        assigned_info = f"\n👤 <b>Назначил:</b> {assigned_by_name}" if assigned_by_name else ""
        
        notification_text = f"""🎯 <b>Вам назначен наставник!</b>

👨‍🏫 <b>Ваш наставник:</b> {mentor_name}

📋 <b>Контактная информация:</b>
{contact_info}{assigned_info}

💡 <b>Что дальше?</b>
• Свяжитесь с наставником для знакомства
• Обсудите план обучения и цели стажировки
• Задавайте вопросы и просите помощь при необходимости
• Наставник поможет вам с тестами и заданиями

🎯 <b>Удачи в обучении!</b>"""

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        # Создаем клавиатуру с полезными кнопками
        keyboard_buttons = []
        
        # Кнопка для связи с наставником (если есть username)
        if mentor_username:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="💬 Написать наставнику", 
                    url=f"https://t.me/{mentor_username}"
                )
            ])
        
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="📋 Мои доступные тесты", callback_data="available_tests")],
            [InlineKeyboardButton(text="👨‍🏫 Информация о наставнике", callback_data="my_mentor_info")]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await bot.send_message(
            chat_id=trainee_tg_id,
            text=notification_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        logger.info(f"Уведомление о назначении наставника '{mentor_name}' отправлено стажеру {trainee_tg_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о наставнике стажеру {trainee_tg_id}: {e}")
        return False 

async def send_notification_about_new_trainee(session: AsyncSession, bot, mentor_id: int, trainee_id: int, assigned_by_id: int):
    """Отправка уведомления наставнику о назначении ему нового стажёра"""
    try:
        # Получаем данные о наставнике
        mentor = await get_user_by_id(session, mentor_id)
        if not mentor:
            logger.error(f"Наставник с ID {mentor_id} не найден")
            return False
            
        # Получаем данные о стажере
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            logger.error(f"Стажер с ID {trainee_id} не найден")
            return False
            
        # Получаем данные о том, кто назначил
        assigned_by = await get_user_by_id(session, assigned_by_id)
        if not assigned_by:
            logger.error(f"Пользователь назначивший с ID {assigned_by_id} не найден")
            return False
        
        await send_trainee_assignment_notification(
            bot=bot,
            mentor_tg_id=mentor.tg_id,
            trainee_name=trainee.full_name,
            trainee_phone=trainee.phone_number,
            trainee_username=trainee.username,
            trainee_registration_date=trainee.registration_date.strftime('%d.%m.%Y'),
            assigned_by_name=assigned_by.full_name
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о назначении стажёра: {e}")
        return False

async def send_trainee_assignment_notification(bot, mentor_tg_id: int, trainee_name: str, trainee_phone: str, trainee_username: str = None, trainee_registration_date: str = None, assigned_by_name: str = None):
    """Отправка уведомления наставнику о назначении ему нового стажёра"""
    try:
        # Формируем контактную информацию стажёра
        contact_info = f"📞 <b>Телефон:</b> {trainee_phone}"
        if trainee_username:
            contact_info += f"\n📧 <b>Telegram:</b> @{trainee_username}"
        else:
            contact_info += f"\n📧 <b>Telegram:</b> не указан"
        
        if trainee_registration_date:
            contact_info += f"\n📅 <b>Дата регистрации:</b> {trainee_registration_date}"
        
        assigned_info = f"\n👤 <b>Назначил:</b> {assigned_by_name}" if assigned_by_name else ""
        
        notification_text = f"""👨‍🏫 <b>Вам назначен новый стажёр!</b>

👤 <b>Стажёр:</b> {trainee_name}

📋 <b>Контактная информация:</b>
{contact_info}{assigned_info}

💡 <b>Что делать дальше?</b>
• Свяжитесь со стажёром для знакомства
• Обсудите план обучения и цели стажировки
• Предоставьте доступ к необходимым тестам
• Помогайте с вопросами и заданиями
• Отслеживайте прогресс обучения

🎯 <b>Успехов в наставничестве!</b>"""

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        # Создаем клавиатуру с полезными кнопками
        keyboard_buttons = []
        
        # Кнопка для связи со стажёром (если есть username)
        if trainee_username:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="💬 Написать стажёру", 
                    url=f"https://t.me/{trainee_username}"
                )
            ])
        
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="👥 Мои стажёры", callback_data="my_trainees")],
            [InlineKeyboardButton(text="📊 Предоставить доступ к тестам", callback_data="grant_test_access")]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await bot.send_message(
            chat_id=mentor_tg_id,
            text=notification_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        logger.info(f"Уведомление о назначении стажёра '{trainee_name}' отправлено наставнику {mentor_tg_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о стажёре наставнику {mentor_tg_id}: {e}")
        return False 

async def send_notification_about_new_trainee_registration(session: AsyncSession, bot, trainee_id: int):
    """Отправка уведомления всем рекрутерам о регистрации нового стажёра"""
    try:
        # Получаем данные о стажере
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            logger.error(f"Стажер с ID {trainee_id} не найден")
            return False
            
        # Получаем всех рекрутеров
        recruiters = await get_users_by_role(session, "Рекрутер")
        
        if not recruiters:
            logger.info("Нет рекрутеров в системе для отправки уведомлений")
            return True
        
        # Отправляем уведомления каждому рекрутеру
        success_count = 0
        for recruiter in recruiters:
            try:
                await send_new_trainee_registration_notification(
                    bot=bot,
                    recruiter_tg_id=recruiter.tg_id,
                    trainee_name=trainee.full_name,
                    trainee_phone=trainee.phone_number,
                    trainee_username=trainee.username,
                    trainee_registration_date=trainee.registration_date.strftime('%d.%m.%Y %H:%M')
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления рекрутеру {recruiter.tg_id}: {e}")
        
        logger.info(f"Уведомления о новом стажёре отправлены {success_count}/{len(recruiters)} рекрутерам")
        return success_count > 0
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений о новом стажёре: {e}")
        return False

async def send_new_trainee_registration_notification(bot, recruiter_tg_id: int, trainee_name: str, trainee_phone: str, trainee_username: str = None, trainee_registration_date: str = None):
    """Отправка уведомления рекрутеру о регистрации нового стажёра"""
    try:
        # Формируем контактную информацию стажёра
        contact_info = f"📞 <b>Телефон:</b> {trainee_phone}"
        if trainee_username:
            contact_info += f"\n📧 <b>Telegram:</b> @{trainee_username}"
        else:
            contact_info += f"\n📧 <b>Telegram:</b> не указан"
        
        if trainee_registration_date:
            contact_info += f"\n📅 <b>Дата регистрации:</b> {trainee_registration_date}"
        
        notification_text = f"""🎉 <b>Новый стажёр зарегистрировался!</b>

👤 <b>Стажёр:</b> {trainee_name}

📋 <b>Контактная информация:</b>
{contact_info}

💡 <b>Рекомендуемые действия:</b>
• Свяжитесь со стажёром для знакомства
• Назначьте подходящего наставника
• Предоставьте доступ к начальным тестам
• Проведите вводный инструктаж

⚡ <b>Быстрые действия:</b>"""

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        # Создаем клавиатуру с полезными кнопками
        keyboard_buttons = []
        
        # Кнопка для связи со стажёром (если есть username)
        if trainee_username:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="💬 Написать стажёру", 
                    url=f"https://t.me/{trainee_username}"
                )
            ])
        
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="👨‍🏫 Назначить наставника", callback_data="assign_mentor")],
            [InlineKeyboardButton(text="👥 Список новых стажёров", callback_data="new_trainees_list")],
            [InlineKeyboardButton(text="📊 Предоставить доступ к тестам", callback_data="grant_test_access")]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await bot.send_message(
            chat_id=recruiter_tg_id,
            text=notification_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        logger.info(f"Уведомление о новом стажёре '{trainee_name}' отправлено рекрутеру {recruiter_tg_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о новом стажёре рекрутеру {recruiter_tg_id}: {e}")
        return False 
from aiogram.fsm.state import StatesGroup, State

class AuthStates(StatesGroup):
    """Состояния для процесса авторизации"""
    waiting_for_auth = State()
 
class RegistrationStates(StatesGroup):
    """Состояния для процесса регистрации"""
    waiting_for_full_name = State()
    waiting_for_phone = State()
    waiting_for_role = State()
    waiting_for_admin_token = State()

class AdminStates(StatesGroup):
    """Состояния для административной панели"""
    waiting_for_user_selection = State()
    waiting_for_user_action = State()
    waiting_for_role_change = State()
    waiting_for_confirmation = State()

    waiting_for_role_selection = State()
    waiting_for_permission_action = State()
    waiting_for_permission_selection = State()
    waiting_for_permission_confirmation = State()

class TestCreationStates(StatesGroup):
    """Состояния для создания тестов"""
    waiting_for_test_name = State()
    waiting_for_materials = State()
    waiting_for_description = State()
    
    # Цикл добавления вопросов
    waiting_for_question_type = State()
    waiting_for_question_text = State()
    
    # Пошаговое добавление вариантов
    waiting_for_option = State()
    
    waiting_for_answer = State()
    waiting_for_points = State()
    waiting_for_more_questions = State()
    
    # Финальные настройки
    waiting_for_threshold = State()
    waiting_for_stage_selection = State()
    waiting_for_final_confirmation = State()
    
    # Редактирование
    waiting_for_edit_action = State()
    waiting_for_new_test_name = State()
    waiting_for_new_test_description = State()
    waiting_for_new_threshold = State()
    waiting_for_new_stage = State()
    waiting_for_new_attempts = State()
    waiting_for_new_materials = State()
    
    waiting_for_question_selection = State()
    waiting_for_question_action = State()
    waiting_for_question_edit = State()
    waiting_for_answer_edit = State()
    waiting_for_points_edit = State()

class TestTakingStates(StatesGroup):
    """Состояния для прохождения тестов"""
    waiting_for_test_selection = State()
    waiting_for_test_start = State()
    taking_test = State()
    waiting_for_answer = State()
    test_completed = State()

class MentorshipStates(StatesGroup):
    """Состояния для работы с наставничеством"""
    waiting_for_trainee_selection = State()
    waiting_for_mentor_selection = State()
    waiting_for_assignment_confirmation = State()
    waiting_for_trainee_action = State()
    waiting_for_test_assignment = State()
    waiting_for_test_selection_for_trainee = State()

class TraineeManagementStates(StatesGroup):
    """Состояния для управления стажерами"""
    waiting_for_trainee_selection = State()
    waiting_for_trainee_action = State()
    waiting_for_test_access_grant = State()
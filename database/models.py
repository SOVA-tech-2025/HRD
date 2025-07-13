from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey, Table, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()


user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True)
)

class User(Base):
    """Модель пользователя"""

    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, nullable=False)
    registration_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    
    # Связи для наставничества
    mentoring_relationships = relationship("Mentorship", foreign_keys="Mentorship.mentor_id", back_populates="mentor")
    trainee_relationships = relationship("Mentorship", foreign_keys="Mentorship.trainee_id", back_populates="trainee")
    
    # Связи для тестов
    created_tests = relationship("Test", back_populates="creator")
    test_results = relationship("TestResult", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, tg_id={self.tg_id}, username={self.username})>"

class Role(Base):
    """Модель роли"""

    __tablename__ = 'roles'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    
    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")
    
    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"


role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id'), primary_key=True)
)

class Permission(Base):
    """Модель прав доступа"""
    
    __tablename__ = 'permissions'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    
    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")
    
    def __repr__(self):
        return f"<Permission(id={self.id}, name={self.name})>"


class InternshipStage(Base):
    """Модель этапов стажировки"""
    
    __tablename__ = 'internship_stages'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    order_number = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=datetime.now)
    
    # Связи
    tests = relationship("Test", back_populates="stage")
    
    def __repr__(self):
        return f"<InternshipStage(id={self.id}, name={self.name}, order={self.order_number})>"


class Test(Base):
    """Модель тестов"""
    
    __tablename__ = 'tests'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    threshold_score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False, default=0)
    material_link = Column(String, nullable=True)
    material_file_path = Column(String, nullable=True)
    stage_id = Column(Integer, ForeignKey('internship_stages.id'), nullable=True)
    creator_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    
    # Расширенные настройки
    shuffle_questions = Column(Boolean, default=False)
    max_attempts = Column(Integer, default=1) # 0 - бесконечно
    
    # Связи
    stage = relationship("InternshipStage", back_populates="tests")
    creator = relationship("User", back_populates="created_tests")
    questions = relationship("TestQuestion", back_populates="test", cascade="all, delete-orphan")
    results = relationship("TestResult", back_populates="test")
    
    def __repr__(self):
        return f"<Test(id={self.id}, name={self.name}, threshold={self.threshold_score})>"


class TestQuestion(Base):
    """Модель вопросов теста"""
    
    __tablename__ = 'test_questions'
    
    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=False)
    question_number = Column(Integer, nullable=False)
    question_type = Column(String, nullable=False, default='text')  # text, single_choice, multiple_choice, yes_no, number
    question_text = Column(Text, nullable=False)
    options = Column(JSONB, nullable=True)
    correct_answer = Column(String, nullable=False) # Для multi_choice - JSON-строка
    points = Column(Float, nullable=False, default=1)
    penalty_points = Column(Float, nullable=False, default=0) # Штраф за неправильный ответ
    created_date = Column(DateTime, default=datetime.now)
    
    # Связи
    test = relationship("Test", back_populates="questions")
    
    def __repr__(self):
        return f"<TestQuestion(id={self.id}, test_id={self.test_id}, number={self.question_number})>"


class TestResult(Base):
    """Модель результатов прохождения тестов"""
    
    __tablename__ = 'test_results'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=False)
    score = Column(Float, nullable=False)
    max_possible_score = Column(Float, nullable=False)
    is_passed = Column(Boolean, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    answers = Column(Text, nullable=True)  # JSON строка с ответами пользователя
    answers_details = Column(JSONB, nullable=True) # Детальная информация по ответам (время, правильность)
    wrong_answers = Column(JSONB, nullable=True) # Сохранение неверных ответов
    created_date = Column(DateTime, default=datetime.now)
    
    # Связи
    user = relationship("User", back_populates="test_results")
    test = relationship("Test", back_populates="results")
    
    def __repr__(self):
        return f"<TestResult(id={self.id}, user_id={self.user_id}, test_id={self.test_id}, score={self.score})>"


class Mentorship(Base):
    """Модель наставничества (связь стажер-наставник)"""
    
    __tablename__ = 'mentorships'
    
    id = Column(Integer, primary_key=True)
    mentor_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    trainee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    assigned_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Кто назначил (рекрутер)
    assigned_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    
    # Связи
    mentor = relationship("User", foreign_keys=[mentor_id], back_populates="mentoring_relationships")
    trainee = relationship("User", foreign_keys=[trainee_id], back_populates="trainee_relationships")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])
    
    def __repr__(self):
        return f"<Mentorship(id={self.id}, mentor_id={self.mentor_id}, trainee_id={self.trainee_id})>"


class TraineeTestAccess(Base):
    """Модель доступа стажеров к тестам"""
    
    __tablename__ = 'trainee_test_access'
    
    id = Column(Integer, primary_key=True)
    trainee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=False)
    granted_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Наставник, который открыл доступ
    granted_date = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    
    # Связи
    trainee = relationship("User", foreign_keys=[trainee_id])
    test = relationship("Test")
    granted_by = relationship("User", foreign_keys=[granted_by_id])
    
    def __repr__(self):
        return f"<TraineeTestAccess(id={self.id}, trainee_id={self.trainee_id}, test_id={self.test_id})>" 
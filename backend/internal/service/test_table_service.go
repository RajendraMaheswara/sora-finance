package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"
)

type TestTableService struct {
	repo *repository.TestTableRepository
}

func NewTestTableService(repo *repository.TestTableRepository) *TestTableService {
	return &TestTableService{repo: repo}
}

func (s *TestTableService) GetAll(ctx context.Context) ([]models.TestTable, error) {
	return s.repo.GetAll(ctx)
}

func (s *TestTableService) GetByID(ctx context.Context, id int64) (*models.TestTable, error) {
	if id <= 0 {
		return nil, errors.New("invalid id")
	}
	return s.repo.GetByID(ctx, id)
}

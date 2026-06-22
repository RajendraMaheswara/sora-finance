package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/auth"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type FinanceDailyHppSummaryRepository struct {
	db *pgxpool.Pool
}

func NewFinanceDailyHppSummaryRepository(db *pgxpool.Pool) *FinanceDailyHppSummaryRepository {
	return &FinanceDailyHppSummaryRepository{db: db}
}

func (r *FinanceDailyHppSummaryRepository) GetAll(ctx context.Context) ([]models.FinanceDailyHppSummary, error) {
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, t_finance_daily_summary_id, m_menu_category_id, name, total_hpp,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM t_finance_daily_hpp_summaries
		WHERE deleted_at IS NULL`
	var args []interface{}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND m_store_id = $1`
		args = append(args, claims.StoreID)
	}
	query += `
		ORDER BY created_at DESC`
	rows, err := r.db.Query(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.FinanceDailyHppSummary
	for rows.Next() {
		var item models.FinanceDailyHppSummary
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.FinanceDailySummaryID, &item.MenuCategoryID, &item.Name,
			&item.TotalHpp, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy,
			&item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *FinanceDailyHppSummaryRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.FinanceDailyHppSummary, error) {
	var item models.FinanceDailyHppSummary
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, t_finance_daily_summary_id, m_menu_category_id, name, total_hpp,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM t_finance_daily_hpp_summaries
		WHERE id = $1 AND deleted_at IS NULL
	`
	args := []interface{}{id}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND m_store_id = $2`
		args = append(args, claims.StoreID)
	}
	err := r.db.QueryRow(ctx, query, args...).Scan(
		&item.ID, &item.StoreID, &item.FinanceDailySummaryID, &item.MenuCategoryID, &item.Name,
		&item.TotalHpp, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy,
		&item.DeletedAt, &item.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}

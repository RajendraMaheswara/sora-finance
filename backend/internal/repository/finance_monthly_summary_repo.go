package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type FinanceMonthlySummaryRepository struct {
	db *pgxpool.Pool
}

func NewFinanceMonthlySummaryRepository(db *pgxpool.Pool) *FinanceMonthlySummaryRepository {
	return &FinanceMonthlySummaryRepository{db: db}
}

func (r *FinanceMonthlySummaryRepository) GetAll(ctx context.Context) ([]models.FinanceMonthlySummary, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, date, total_cash, total_rounding, total_debit, total_ewallet,
		       total_income, total_regulation_outlet, total_regulation_customer, total_hpp,
		       total_discount, total_cost_and_expense, total_net_income, created_at, created_by,
		       updated_at, updated_by, deleted_at, deleted_by
		FROM t_finance_monthly_summaries
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.FinanceMonthlySummary
	for rows.Next() {
		var item models.FinanceMonthlySummary
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.Date, &item.TotalCash, &item.TotalRounding, &item.TotalDebit,
			&item.TotalEwallet, &item.TotalIncome, &item.TotalRegulationOutlet, &item.TotalRegulationCustomer,
			&item.TotalHpp, &item.TotalDiscount, &item.TotalCostAndExpense, &item.TotalNetIncome,
			&item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *FinanceMonthlySummaryRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.FinanceMonthlySummary, error) {
	var item models.FinanceMonthlySummary
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, date, total_cash, total_rounding, total_debit, total_ewallet,
		       total_income, total_regulation_outlet, total_regulation_customer, total_hpp,
		       total_discount, total_cost_and_expense, total_net_income, created_at, created_by,
		       updated_at, updated_by, deleted_at, deleted_by
		FROM t_finance_monthly_summaries
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&item.ID, &item.StoreID, &item.Date, &item.TotalCash, &item.TotalRounding, &item.TotalDebit,
		&item.TotalEwallet, &item.TotalIncome, &item.TotalRegulationOutlet, &item.TotalRegulationCustomer,
		&item.TotalHpp, &item.TotalDiscount, &item.TotalCostAndExpense, &item.TotalNetIncome,
		&item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}

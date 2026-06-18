package repository

import "strconv"

func sqlParam(index int) string {
	return "$" + strconv.Itoa(index)
}

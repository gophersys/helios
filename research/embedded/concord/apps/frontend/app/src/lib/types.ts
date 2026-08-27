export interface ApiResponse<T> {
  data: T;
  errors?: Array<{
    code?: string;
    message: string;
    field?: string;
  }>;
}

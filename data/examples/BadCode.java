import java.sql.*;

public class BadCode {

    public static String password = "admin123";

    public static ResultSet getUser(Connection conn, String id) throws SQLException {
        Statement stmt = conn.createStatement();
        String query = "SELECT * FROM users WHERE id = " + id;
        return stmt.executeQuery(query);
    }

    public static double compute(double x, double y, double z, double a, double b, double c, double d) {
        double r = 0;
        if (x > 0) { r = r + x * 3.14159; }
        if (y > 0) { r = r + y * 3.14159; }
        if (z > 0) { r = r + z * 3.14159; }
        if (a > 0) { r = r + a * 3.14159; }
        if (b > 0) { r = r + b * 3.14159; }
        if (c > 0) { r = r + c * 3.14159; }
        if (d > 0) { r = r + d * 3.14159; }
        return r;
    }

    public static double computeAgain(double x, double y, double z, double a, double b, double c, double d) {
        double r = 0;
        if (x > 0) { r = r + x * 3.14159; }
        if (y > 0) { r = r + y * 3.14159; }
        if (z > 0) { r = r + z * 3.14159; }
        if (a > 0) { r = r + a * 3.14159; }
        if (b > 0) { r = r + b * 3.14159; }
        if (c > 0) { r = r + c * 3.14159; }
        if (d > 0) { r = r + d * 3.14159; }
        return r;
    }

    public static void riskyParse(String input) {
        try {
            int value = Integer.parseInt(input);
            System.out.println(value);
        } catch (Exception e) {
        }
    }

    public static void main(String[] args) {
        System.out.println("Result: " + compute(1, 2, 3, 4, 5, 6, 7));
        riskyParse("not_a_number");
    }
}

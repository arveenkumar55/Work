import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

class CsvObject implements Comparable<CsvObject> {
    String cveId;
    String modDate;
    String pubDate;
    String cvss;
    String cweCode;
    String cweName;
    String summary;
    String accessAuthentication;
    String accessComplexity;
    String accessVector;
    String impactAvailability;
    String impactConfidentiality;
    String impactIntegrity;

    public CsvObject(String line) {
        String[] tokens = getTokens(line);
        cveId = tokens[0];
        modDate = tokens[1];
        pubDate = tokens[2];
        cvss = tokens[3];
        cweCode = tokens[4];
        cweName = tokens[5];
        summary = tokens[6];
        accessAuthentication = tokens[7];
        accessComplexity = tokens[8];
        accessVector = tokens[9];
        impactAvailability = tokens[10];
        impactConfidentiality = tokens[11];
        impactIntegrity = tokens[12];
    }

    private static boolean hasDoubleQuotes(String token) {
        return !token.endsWith("\"\"\"") && (token.endsWith("\"\"") || !token.endsWith("\""));
    }

    private String[] getTokens(String line) {
        String[] tokens = line.split(",", -1);
        final List<String> normalizedTokens = new ArrayList<>();
        for (int i = 0; i < tokens.length; i++) {
            String token = tokens[i];
            if (token.startsWith("\"")) {
                boolean alignIndex = false;
                for (; i < tokens.length && hasDoubleQuotes(token); i++) {
                    alignIndex = true;
                    token += tokens[i].strip();
                }

                if (alignIndex) i--;
            }

            normalizedTokens.add(token);
        }

        return normalizedTokens.toArray(new String[0]);
    }

    private int impactValue(String impact) {
        switch (impact) {
            case "COMPLETE":
                return 3;
            case "PARTIAL":
                return 2;
            case "NONE":
                return 1;
            default:
                return 0;
        }
    }

    private int accessValue(String access) {
        switch (access) {
            case "HIGH":
                return 3;
            case "MEDIUM":
                return 2;
            case "LOW":
                return 1;
            default:
                return 0;
        }
    }

    private double impactToAccessRatio() {
        return ((double) impactValue(impactAvailability) + impactValue(impactIntegrity) + impactValue(impactConfidentiality)) / accessValue(accessComplexity);
    }

    @Override
    public int compareTo(CsvObject o) {
        return Double.compare(impactToAccessRatio(), o.impactToAccessRatio());
    }

    @Override
    public String toString() {
        return String.format("%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s", cveId, modDate, pubDate, cvss, cweCode, cweName, summary, accessAuthentication, accessComplexity, accessVector, impactAvailability, impactConfidentiality, impactIntegrity);
    }
}

public class Main {

    private static String header;

    public static void main(String[] args) {
        try (BufferedReader reader = new BufferedReader(new FileReader("dataset.csv"))) {
            List<String> lines = readCsv(reader);
            var csv = lines.stream().map(CsvObject::new).sorted(CsvObject::compareTo).collect(Collectors.toList());
            System.out.println(header);
            for (CsvObject csvObject : csv) {
                System.out.println(csvObject);
            }
        } catch (IOException e) {
            e.printStackTrace();
        }

    }

    private static List<String> readCsv(BufferedReader reader) {
        List<String> lines = reader.lines().collect(Collectors.toList());
        header = lines.get(0);
        lines = lines.subList(1, lines.size());
        for (int i = 0; i < lines.size(); i++) {
            String line = lines.get(i);
            if (!line.startsWith("CVE-")) {
                lines.set(i - 1, lines.get(i - 1) + "\n" + line);
                lines.remove(i);
                i--;
            }
        }
        return lines;
    }

}

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
public class ApiFetcher {
    private static final Map<String, List<String>> SECTOR_PEERS = Map.of(
        "IT",       List.of("TCS", "INFY", "WIPRO", "HCLTECH"),
        "BANKS",    List.of("HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK"),
        "ENERGY",   List.of("RELIANCE", "ONGC", "BPCL"),
        "FMCG",     List.of("ITC", "HINDUNILVR", "NESTLEIND"),
        "TELECOM",  List.of("BHARTIARTL", "IDEA", "INDUSTOWER"),
        "CAPGOODS", List.of("LT", "BHEL", "SIEMENS")
    );
    public static String fetchAll(String ticker, String generationId, String[] dynamicPeers, boolean skipYahoo) {
        try {
            Files.createDirectories(Path.of("json"));
            Files.createDirectories(Path.of("cache"));
        } catch (IOException e) {
            System.err.println("  [Java/ApiFetcher] Could not create directories: " + e.getMessage());
            return null;
        }

        if (skipYahoo) {
            // FAST LANE: Skip Python Yahoo scrape, assume cached data exists on disk.
            System.out.println("  [Java/ApiFetcher] FAST LANE: Skipping Yahoo scrape (cached data).");
            try {
                Path cacheDir = Path.of("cache", ticker);
                Files.copy(cacheDir.resolve("yf_cache.json"), Path.of("json", generationId + "_yf_temp.json"), StandardCopyOption.REPLACE_EXISTING);
                Path peersCache = cacheDir.resolve("peers_cache.json");
                if (Files.exists(peersCache)) {
                    Files.copy(peersCache, Path.of("json", generationId + "_peers_temp.json"), StandardCopyOption.REPLACE_EXISTING);
                }
            } catch (IOException e) {
                System.err.println("  [Java/ApiFetcher] Failed to copy cached data: " + e.getMessage());
            }
            // Still fetch fresh news every time.
            NewsManager.fetchNews(ticker, generationId, skipYahoo);
            return "json/" + generationId + "_yf_temp.json";
        }

        // SLOW LANE: Full Yahoo scrape via Python tricker.py
        System.out.println("  [Java/ApiFetcher] Starting stealth Yahoo ingestion via python/tricker.py for " + ticker);
        List<String> peerTickers = new ArrayList<>();
        if (dynamicPeers != null && dynamicPeers.length > 0) {
            // Use dynamic peers injected by the Python backend
            for (String p : dynamicPeers) {
                String full = p.contains(".") ? p : p + ".NS";
                if (!full.equals(ticker)) {
                    peerTickers.add(full);
                }
            }
            System.out.println("  [Java/ApiFetcher] Using dynamic peers: " + peerTickers);
        } else {
            // Fallback to hardcoded sector map for standalone CLI usage
            String base = ticker.replace(".NS", "");
            for (Map.Entry<String, List<String>> entry : SECTOR_PEERS.entrySet()) {
                if (entry.getValue().contains(base)) {
                    for (String p : entry.getValue()) {
                        String full = p + ".NS";
                        if (!full.equals(ticker)) {
                            peerTickers.add(full);
                        }
                    }
                    break;
                }
            }
        }
        List<String> cmd = new ArrayList<>();
        String pythonBin = System.getenv("VIRTUAL_ENV") != null ? System.getenv("VIRTUAL_ENV") + "/bin/python" : "python3";
        cmd.add(pythonBin);
        cmd.add("python/tricker.py");
        cmd.add(generationId);
        cmd.add(ticker);
        cmd.addAll(peerTickers);
        System.out.println("  [Java/ApiFetcher] Executing: " + String.join(" ", cmd));
        try {
            ProcessBuilder pb = new ProcessBuilder(cmd);
            pb.redirectErrorStream(true);
            Process proc = pb.start();
            try (BufferedReader br = new BufferedReader(new InputStreamReader(proc.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = br.readLine()) != null) {
                    System.out.println("    " + line);
                }
            }
            int exitCode = proc.waitFor();
            if (exitCode != 0) {
                System.err.println("  [Java/ApiFetcher] FATAL: python/tricker.py exited with code " + exitCode);
            } else {
                System.out.println("  [Java/ApiFetcher] Successfully fetched Yahoo data.");
                NewsManager.fetchNews(ticker, generationId, false);
            }
        } catch (Exception e) {
            System.err.println("  [Java/ApiFetcher] Exception running Python tricker: " + e.getMessage());
            e.printStackTrace();
        }
        return "json/yf_temp.json";
    }
}

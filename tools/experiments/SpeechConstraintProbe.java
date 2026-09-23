import com.sao.engine.SAOFence;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;

public final class SpeechConstraintProbe {
    public static void main(String[] args) throws Exception {
        String mode = args.length > 1 ? args[1] : "actual";
        if (!mode.equals("actual") && !mode.equals("all-accept") && !mode.equals("all-refuse")) {
            throw new IllegalArgumentException("unknown control mode");
        }
        var decoder = Base64.getDecoder();
        for (String line : Files.readAllLines(Path.of(args[0]), StandardCharsets.UTF_8)) {
            String[] fields = line.split("\\t", -1);
            if (fields.length != 3) throw new IllegalArgumentException("bad fixture");
            String claims = new String(decoder.decode(fields[1]), StandardCharsets.UTF_8);
            String filling = new String(decoder.decode(fields[2]), StandardCharsets.UTF_8);
            boolean observed = SAOFence.sayable(claims, filling);
            // Instrument controls deliberately corrupt the reported observation.
            if (mode.equals("all-accept")) observed = true;
            if (mode.equals("all-refuse")) observed = false;
            System.out.println(fields[0] + "\t" + observed);
        }
    }
}

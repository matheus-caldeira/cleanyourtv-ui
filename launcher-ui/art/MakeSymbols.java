import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.geom.*;
import java.awt.image.BufferedImage;
import java.io.File;

/**
 * The two symbols Explore needs that didn't come with Free My TV, drawn in the same style as the Material Symbols in
 * app/assets/symbols (white on transparent, ~150 px, rounded strokes). Run: java art/MakeSymbols.java
 */
public class MakeSymbols {
    public static void main(String[] args) throws Exception {
        write("mic", g -> {
            g.draw(new RoundRectangle2D.Double(57, 15, 36, 72, 36, 36));
            g.draw(new Arc2D.Double(35, 27, 80, 86, 180, 180, Arc2D.OPEN));
            g.draw(new Line2D.Double(75, 113, 75, 136));
        });
        write("search", g -> {
            g.draw(new Ellipse2D.Double(22, 22, 78, 78));
            g.draw(new Line2D.Double(90, 90, 128, 128));
        });
        write("tune", g -> {
            double[] ys = {34, 75, 116}, knobs = {92, 50, 78};
            for (int i = 0; i < 3; i++) {
                g.draw(new Line2D.Double(18, ys[i], 132, ys[i]));
                g.fill(new Ellipse2D.Double(knobs[i] - 15, ys[i] - 15, 30, 30));
            }
        });
    }

    interface Drawing { void draw(Graphics2D g); }

    static void write(String name, Drawing d) throws Exception {
        BufferedImage img = new BufferedImage(150, 150, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g = img.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_STROKE_CONTROL, RenderingHints.VALUE_STROKE_PURE);
        g.setColor(Color.WHITE);
        g.setStroke(new BasicStroke(13, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
        d.draw(g);
        g.dispose();
        ImageIO.write(img, "png", new File("app/assets/symbols/" + name + ".png"));
    }
}
